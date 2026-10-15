"""Fail-closed native launcher dependency and hardening inspection; no execution."""
from pathlib import Path
import hashlib
import json
import pefile

OS_IMPORTS = frozenset({'kernel32.dll', 'user32.dll', 'shell32.dll', 'advapi32.dll',
                        'version.dll', 'bcrypt.dll'})


def audit_launcher(path):
    path = Path(path)
    with pefile.PE(str(path)) as image:
        if image.FILE_HEADER.Machine != 0x8664:
            raise ValueError('Launcher must be a native x64 PE')
        if image.OPTIONAL_HEADER.Subsystem != 2:
            raise ValueError('Launcher must use the Windows GUI subsystem')
        imports = {row.dll.decode('ascii').casefold()
                   for name in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT')
                   for row in getattr(image, name, [])}
        if not imports or imports - OS_IMPORTS:
            raise ValueError('Launcher imports non-OS or runtime DLLs: ' + ', '.join(sorted(imports - OS_IMPORTS)))
        flags = image.OPTIONAL_HEADER.DllCharacteristics
        if flags & 0x160 != 0x160:  # HIGH_ENTROPY_VA | DYNAMIC_BASE | NX_COMPAT
            raise ValueError('Launcher ASLR/NX hardening is absent')
        load_config = getattr(image, 'DIRECTORY_ENTRY_LOAD_CONFIG', None)
        if not load_config or not load_config.struct.SecurityCookie:
            raise ValueError('Launcher has no stack-cookie load configuration')
        if load_config.struct.DependentLoadFlags != 0x800:
            raise ValueError('Launcher dependency search is not System32-only')
        manifests = []
        for entry in getattr(image, 'DIRECTORY_ENTRY_RESOURCE', []).entries:
            if entry.id == 24:
                for name in entry.directory.entries:
                    for language in name.directory.entries:
                        data = language.data.struct
                        manifests.append(image.get_data(data.OffsetToData, data.Size))
        if len(manifests) != 1 or b'asInvoker' not in manifests[0] or b'PerMonitorV2' not in manifests[0]:
            raise ValueError('Launcher privilege/DPI manifest is missing or ambiguous')
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': path.stat().st_size, 'imports': sorted(imports),
            'crt_imports': [], 'system32_dependent_load_flags': 0x800,
            'stack_cookie': True, 'aslr_nx': True, 'executed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('launcher', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_launcher(args.launcher), indent=2))
