"""Split only the retained Qt source carrier; preserve the exact frozen source ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from verify_split_source import digest, safe, verify

QT = 'dependencies/qtwebengine-everywhere-src-6.11.2.tar.xz'
QT_HASH = '6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163'
ORIGINAL = 'e86195cf4c1a8cac00a873dd645ef5d596eab48b8d4260584be8d21dc80cb3ce'
OVERLAY = ('installer/MastixaManager.iss', 'installer/vc_redist_prerequisite.iss',
           'packaging/vc-redist-lock.json', 'packaging/repackage_rc2.ps1',
           'packaging/split_rc2_source.py', 'packaging/verify_split_source.py',
           'docs/WINDOWS_RC2_REPACKAGING.md', 'tests/test_rc2_repackaging.py',
           'tests/test_windows_crt_policy.py')


def zip_files(root, paths, output):
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(paths):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 11, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED if name.endswith(('.zip', '.xz', '.gz', '.bz2')) else zipfile.ZIP_DEFLATED
            with (root/name).open('rb') as source, z.open(info, 'w', force_zip64=True) as target:
                shutil.copyfileobj(source, target, 1024*1024)


def assemble(original, root, out, installer):
    if digest(original) != ORIGINAL:
        raise ValueError('Original full delivery hash mismatch')
    if out.exists():
        raise ValueError('Output must be absent; preserve all previous outputs')
    out.mkdir(parents=True)
    main = out/'recipient'; main.mkdir()
    assets = out/'assets'; assets.mkdir()
    with zipfile.ZipFile(original) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
        if len(names) != 324 or len({n.casefold() for n in names}) != len(names):
            raise ValueError('Unexpected original member count')
        for name in names:
            target = assets/Path(QT).name if name == QT else safe(main, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as source, target.open('xb') as destination:
                shutil.copyfileobj(source, destination, 1024*1024)
    manifest = json.loads((main/'RECIPIENT_MANIFEST.json').read_text(encoding='utf-8'))
    # Verify every material against the original manifest before changing delivery metadata.
    for row in manifest['files']:
        p = assets/Path(QT).name if row['path'] == QT else safe(main, row['path'])
        if p.stat().st_size != row['size'] or digest(p) != row['sha256']:
            raise ValueError('Original source material changed: '+row['path'])
    if digest(assets/Path(QT).name) != QT_HASH:
        raise ValueError('Retained full Qt carrier identity mismatch')
    zip_files(root, OVERLAY, main/'application/installer-repack-source.zip')
    (main/'verify_package.py').write_bytes((root/'packaging/verify_split_source.py').read_bytes())
    (main/'INSTALLER_REPACKAGING.md').write_bytes((root/'docs/WINDOWS_RC2_REPACKAGING.md').read_bytes())
    prefix = ('Split delivery update — 2026-10-11. The full QtPdf/PDFium source carrier is a\n'
              'MANDATORY separate asset: qtwebengine-everywhere-src-6.11.2.tar.xz,\n'
              '580351104 bytes, SHA-256 '+QT_HASH+'.\n'
              'Place it at dependencies/qtwebengine-everywhere-src-6.11.2.tar.xz or run\n'
              'python -B verify_package.py <source-root> --assets <asset-dir>.\n'
              'The current verifier requires independently installed Python 3.11 or later.\n'
              'The main ZIP alone is incomplete. Both files form the complete offline set.\n'
              'Publisher URLs are NOT PUBLISHED; equivalent anonymous access remains required.\n'
              'The unchanged original source and its old installer receipts are retained below.\n'
              'New installer source is application/installer-repack-source.zip. Read\n'
              'INSTALLER_REPACKAGING.md before applying this overlay to a fresh source copy.\n'
              'The overlay changes installer controls only; never patch the frozen payload.\n'
              'Old native PASS receipts do not qualify the changed installer.\n\n---\n\n')
    for name in ('README.md','BUILD_INSTRUCTIONS.md','DEPENDENCY_SOURCES.md','CURRENT_STATUS.md','PUBLICATION_CHECKLIST.md'):
        p=main/name; p.write_text(prefix+p.read_text(encoding='utf-8'),encoding='utf-8')
    instructions = main/'BUILD_INSTRUCTIONS.md'
    instructions.write_text(instructions.read_text(encoding='utf-8') +
        '\n## Building the repack installer\n\n'
        'For the old exact frozen payload, retain its original fixed-public-source.zip.\n'
        'To compile the changed installer, apply installer-repack-source.zip to a fresh\n'
        'extracted source copy. Acquire the unmodified official runtime pinned by\n'
        'packaging/vc-redist-lock.json from a properly licensed Visual Studio installation;\n'
        'verify Microsoft signature, version, size and SHA-256. This source package\n'
        'does not include the proprietary Microsoft executable.\n'
        'Use Inno Setup with /DMyAppSourceDir=<unchanged-payload> and\n'
        '/DMyVcRedistPath=<verified-vc_redist.x64.exe>, /O<fresh-output-directory>,\n'
        'and installer/MastixaManager.iss. packaging/repackage_rc2.ps1 supplies the\n'
        'strict publisher-only 559-file/manifest guard for retained RC2 bytes.\n'
        'For a full recipient rebuild, preserve the original source recipe and all\n'
        'supplier locks, then independently qualify the resulting modified bytes.\n',encoding='utf-8')
    asset={'filename':Path(QT).name,'materialized_path':QT,'size':580351104,'sha256':QT_HASH,
           'component':'QtPdf/PDFium','version':'6.11.2','required':True,'published_url':None,
           'role':'Untrimmed QtPdf/PDFium preferred source, nested sources, CMake/GN and licenses'}
    manifest['external_assets']=[asset]
    manifest['delivery_route']='Main ZIP plus mandatory versioned hash-pinned full Qt source asset; both required for complete offline delivery'
    manifest['original_delivery_sha256']=ORIGINAL
    manifest['original_binary_identity']=manifest.pop('binary_identity')
    manifest['binary_identity']={'installer_sha256':digest(installer),'installer_size':installer.stat().st_size,
        'installer_name':installer.name,'frozen_exe_sha256':manifest['original_binary_identity']['frozen_exe_sha256'],
        'payload_reference':'original_binary_identity.members_sha256: 559 MastixaManager/ files unchanged',
        'qualification':'NOT TESTED: changed installer native lifecycle/runtime/PDF checks pending'}
    manifest['status']['matching_source_binding']='PASS: exact frozen source plus installer overlay; native qualification pending'
    manifest['status']['new_installer_native_qualification']='NOT TESTED'
    manifest['status']['microsoft_redistribution']='CONDITIONAL: final channel/assent review pending'
    manifest['original_native_qualification']=manifest.pop('native_qualification')
    manifest['native_qualification']={'new_installer':'NOT TESTED','original_installer_receipts':'original_native_qualification only; not inherited'}
    for row in manifest['component_obligations']:
        if row.get('component') == 'QtPdf/PDFium':
            row['source_delivery_asset']=asset
            row['instructions'].append('INSTALLER_REPACKAGING.md')
    manifest['installer_repack_source']={'path':'application/installer-repack-source.zip',
        'sha256':digest(main/'application/installer-repack-source.zip'),
        'members_sha256':{name:digest(root/name) for name in OVERLAY},
        'apply_to':'Fresh extraction of unchanged application/fixed-public-source.zip; installer-only controls'}
    manifest['mandatory_material_classes']['public_access']='NOT PUBLISHED: both main ZIP and Qt asset required'
    manifest['mandatory_material_classes']['final_artifact_binding']='New installer SHA-256, exact original frozen source and separate installer overlay; payload hash verification at compile; native checks pending'
    manifest['mandatory_material_classes']['licenses_notices']='Original 219 legal files and archive notices unchanged; INSTALLER_REPACKAGING.md adds separate Microsoft prerequisite notice'
    manifest['shipping_policy']='Original frozen payload unchanged; installer alone adds unmodified proprietary Microsoft runtime; source companions do not redistribute that executable'
    # Re-index local edits and the unchanged external source asset.
    roles={r['path']:r.get('role','Source material') for r in manifest['files']}
    files=[p for p in main.rglob('*') if p.is_file() and p.name not in ('RECIPIENT_MANIFEST.json','SHA256SUMS')]
    manifest['files']=[{'path':p.relative_to(main).as_posix(),'size':p.stat().st_size,'sha256':digest(p),
                        'role':roles.get(p.relative_to(main).as_posix(),'Repack installer source/control/notice')} for p in sorted(files)]
    manifest['files'].append({'path':QT,'size':asset['size'],'sha256':QT_HASH,'role':asset['role'],'storage':'external-required'})
    (main/'RECIPIENT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    sums={r['path']:r['sha256'] for r in manifest['files']}
    sums['RECIPIENT_MANIFEST.json']=digest(main/'RECIPIENT_MANIFEST.json')
    (main/'SHA256SUMS').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(sums.items())),encoding='utf-8')
    result=verify(main,assets)
    output=out/'MastixaManager-1.0.0-rc.2-repack-source.zip'
    zip_files(main,[p.relative_to(main).as_posix() for p in main.rglob('*') if p.is_file()],output)
    public=out/'delivery-index.json'
    index={'schema':1,'version':'1.0.0-rc.2-repack-20261011','public_urls':None,'distribution':'NO-GO',
        'main_source':{'filename':output.name,'size':output.stat().st_size,'sha256':digest(output)},
        'qt_source_asset':asset,'installer':manifest['binary_identity'],
        'retention':'While binaries available and at least five years after last distribution'}
    public.write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'verification':result,'delivery':index}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--installer',type=Path,required=True);a=p.parse_args()
    assemble(a.original,a.root,a.out,a.installer)
