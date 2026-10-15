/* SPDX-License-Identifier: AGPL-3.0-only
 * Windows x64 /NODEFAULTLIB entry point. Uses only Windows system APIs.
 * Does not import Python/Qt, write registry/preferences, or fetch/run VC Redist.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include "resource.h"
#include "runtime_policy.h"
#include "arguments.h"
#include "job_child.h"

int MastixaInitializeCookie(void);
static const WCHAR *const runtime_files[] = { MASTIXA_DLL_LIST };
static enum VcResult last_result;
static WCHAR module_path[32768];
static WCHAR engine_path[32768];
static WCHAR engine_directory[32768];

static void Clear(void *destination, SIZE_T count)
{
    volatile BYTE *p = (volatile BYTE *)destination;
    while (count--) *p++ = 0; /* volatile: no compiler-generated CRT memset */
}
static unsigned int Length(const WCHAR *value)
{
    unsigned int n = 0;
    while (value[n]) ++n;
    return n;
}
static int Copy(WCHAR *out, unsigned int capacity, const WCHAR *value)
{
    unsigned int used = 0;
    out[0] = 0;
    while (*value) if (!VcPut(out, capacity, &used, *value++)) return 0;
    return 1;
}
static int Append(WCHAR *out, unsigned int capacity, const WCHAR *value)
{
    unsigned int used = Length(out);
    while (*value) if (!VcPut(out, capacity, &used, *value++)) return 0;
    return 1;
}

static VcSample ReadRegistry(REGSAM view)
{
    static const WCHAR *const names[] = { L"Major", L"Minor", L"Bld", L"Rbld" };
    const WCHAR *key_name = L"SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64";
    VcSample result;
    HKEY key;
    DWORD type, bytes, installed, value;
    LSTATUS status;
    unsigned int i;
    Clear(&result, sizeof(result));
    status = RegOpenKeyExW(HKEY_LOCAL_MACHINE, key_name, 0, KEY_QUERY_VALUE | view, &key);
    if (status == ERROR_FILE_NOT_FOUND || status == ERROR_PATH_NOT_FOUND) return result;
    if (status != ERROR_SUCCESS) { result.state = VC_ACCESS_ERROR; return result; }
    bytes = sizeof(installed);
    status = RegQueryValueExW(key, L"Installed", NULL, &type, (BYTE *)&installed, &bytes);
    if (status != ERROR_SUCCESS || type != REG_DWORD || bytes != sizeof(installed) || installed > 1) {
        result.state = status == ERROR_ACCESS_DENIED ? VC_ACCESS_ERROR : VC_INVALID;
        RegCloseKey(key);
        return result;
    }
    if (!installed) { RegCloseKey(key); return result; }
    for (i = 0; i < 4; ++i) {
        bytes = sizeof(value);
        status = RegQueryValueExW(key, names[i], NULL, &type, (BYTE *)&value, &bytes);
        if (status != ERROR_SUCCESS || type != REG_DWORD || bytes != sizeof(value)) {
            result.state = status == ERROR_ACCESS_DENIED ? VC_ACCESS_ERROR : VC_INVALID;
            RegCloseKey(key);
            return result;
        }
        result.version.part[i] = value;
    }
    RegCloseKey(key);
    result.state = VC_VALID;
    return result;
}

static VcSample ReadCanonicalFile(const WCHAR *path)
{
    VcSample result;
    IMAGE_DOS_HEADER dos;
    struct { DWORD signature; IMAGE_FILE_HEADER file; } pe;
    HANDLE file;
    LARGE_INTEGER size, offset;
    DWORD read, ignored, version_size;
    void *version_data;
    VS_FIXEDFILEINFO *version;
    UINT version_length;
    Clear(&result, sizeof(result));
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                       NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND) result.state = VC_ACCESS_ERROR;
        return result;
    }
    result.state = VC_INVALID;
    if (!GetFileSizeEx(file, &size) || size.QuadPart < (LONGLONG)(sizeof(dos) + sizeof(pe)) ||
        !ReadFile(file, &dos, sizeof(dos), &read, NULL) || read != sizeof(dos) ||
        dos.e_magic != IMAGE_DOS_SIGNATURE || dos.e_lfanew < (LONG)sizeof(dos) ||
        dos.e_lfanew > 1024 * 1024 || dos.e_lfanew > size.QuadPart - (LONGLONG)sizeof(pe)) {
        CloseHandle(file);
        return result;
    }
    offset.QuadPart = dos.e_lfanew;
    if (!SetFilePointerEx(file, offset, NULL, FILE_BEGIN) ||
        !ReadFile(file, &pe, sizeof(pe), &read, NULL) || read != sizeof(pe) ||
        pe.signature != IMAGE_NT_SIGNATURE) {
        CloseHandle(file);
        return result;
    }
    CloseHandle(file);
    result.machine = pe.file.Machine;
    version_size = GetFileVersionInfoSizeW(path, &ignored);
    if (!version_size || version_size > 1024 * 1024) return result;
    version_data = HeapAlloc(GetProcessHeap(), 0, version_size);
    if (!version_data) { result.state = VC_ACCESS_ERROR; return result; }
    if (GetFileVersionInfoW(path, 0, version_size, version_data) &&
        VerQueryValueW(version_data, L"\\", (void **)&version, &version_length) &&
        version_length >= sizeof(*version) && version->dwSignature == 0xfeef04bd) {
        result.version.part[0] = HIWORD(version->dwFileVersionMS);
        result.version.part[1] = LOWORD(version->dwFileVersionMS);
        result.version.part[2] = HIWORD(version->dwFileVersionLS);
        result.version.part[3] = LOWORD(version->dwFileVersionLS);
        result.state = VC_VALID;
    }
    HeapFree(GetProcessHeap(), 0, version_data);
    return result;
}

static enum VcResult ProbeRuntime(void)
{
    VcProbe probe;
    WCHAR *system_path;
    UINT length;
    unsigned int i, base_length;
    Clear(&probe, sizeof(probe));
    probe.registry[0] = ReadRegistry(KEY_WOW64_64KEY);
    probe.registry[1] = ReadRegistry(KEY_WOW64_32KEY);
    system_path = (WCHAR *)HeapAlloc(GetProcessHeap(), 0, 32768 * sizeof(WCHAR));
    if (!system_path) return VC_CHECK_ERROR;
    length = GetSystemDirectoryW(system_path, 32768);
    if (!length || length >= 32768 || !Append(system_path, 32768, L"\\")) {
        HeapFree(GetProcessHeap(), 0, system_path);
        return VC_CHECK_ERROR;
    }
    base_length = Length(system_path);
    for (i = 0; i < MASTIXA_DLL_COUNT; ++i) {
        system_path[base_length] = 0;
        if (!Append(system_path, 32768, runtime_files[i])) {
            HeapFree(GetProcessHeap(), 0, system_path);
            return VC_CHECK_ERROR;
        }
        probe.files[i] = ReadCanonicalFile(system_path);
    }
    HeapFree(GetProcessHeap(), 0, system_path);
    return VcEvaluate(&probe);
}

static const WCHAR *Explanation(enum VcResult result)
{
    if (result == VC_CHECK_ERROR)
        return L"Το Mastixa Manager έχει εγκατασταθεί, αλλά δεν ήταν δυνατός ο ασφαλής έλεγχος "
               L"του Microsoft Visual C++ Redistributable x64 " MASTIXA_MIN_TEXT L" ή νεότερου.\r\n\r\n"
               L"Επιλέξτε «Έλεγχος ξανά». Αν το πρόβλημα παραμένει, ελέγξτε ή επιδιορθώστε "
               L"το επίσημο πακέτο Microsoft. Δεν αλλάζουν τα δεδομένα σας.";
    if (result == VC_WRONG_ARCH)
        return L"Το Mastixa Manager έχει εγκατασταθεί, αλλά δεν επαληθεύτηκε συμβατό runtime x64.\r\n\r\n"
               L"Απαιτείται Microsoft Visual C++ Redistributable x64 " MASTIXA_MIN_TEXT L" ή νεότερο "
               L"για Windows x64. Το πακέτο x86 δεν αρκεί.\r\n\r\n"
               L"Εγκαταστήστε το επίσημο πακέτο από Microsoft και επιλέξτε «Έλεγχος ξανά».";
    return L"Το Mastixa Manager έχει εγκατασταθεί. Για να ανοίξει, απαιτείται Microsoft Visual C++ "
           L"Redistributable x64 " MASTIXA_MIN_TEXT L" ή νεότερο, το οποίο λείπει ή είναι παλιότερο.\r\n\r\n"
           L"Επιλέξτε «Λήψη από Microsoft» και εγκαταστήστε το πακέτο ξεχωριστά. Έπειτα επιλέξτε "
           L"«Έλεγχος ξανά». Αν ζητηθεί επανεκκίνηση Windows, κάντε την και ανοίξτε ξανά την εφαρμογή. "
           L"Χωρίς σύνδεση, χρησιμοποιήστε το επίσημο πακέτο που έχετε ήδη αποθηκεύσει.";
}

static INT_PTR CALLBACK PrerequisiteDialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    (void)lparam;
    if (message == WM_INITDIALOG) {
        SendMessageW(window, WM_SETICON, ICON_BIG,
                     (LPARAM)LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(IDI_MASTIXA)));
        SetDlgItemTextW(window, IDC_EXPLANATION, Explanation(last_result));
        return TRUE;
    }
    if (message == WM_COMMAND) {
        if (LOWORD(wparam) == IDC_DOWNLOAD) {
            /* Intentional user click opens the official URL in the browser only.
               Never ShellExecute a downloaded package; never fetch bytes here. */
            if ((INT_PTR)ShellExecuteW(window, L"open", MASTIXA_DOWNLOAD_URL, NULL, NULL, SW_SHOWNORMAL) <= 32)
                MessageBoxW(window, L"Δεν ήταν δυνατό το άνοιγμα της λήψης Microsoft. "
                            L"Ανοίξτε τον σύνδεσμο που εμφανίζεται στον φυλλομετρητή σας.",
                            L"Mastixa Manager", MB_OK | MB_ICONWARNING);
            return TRUE;
        }
        if (LOWORD(wparam) == IDC_RECHECK) {
            last_result = ProbeRuntime();
            if (last_result == VC_READY) EndDialog(window, IDOK);
            else SetDlgItemTextW(window, IDC_EXPLANATION, Explanation(last_result));
            return TRUE;
        }
        if (LOWORD(wparam) == IDCANCEL) { EndDialog(window, IDCANCEL); return TRUE; }
    }
    if (message == WM_CLOSE) { EndDialog(window, IDCANCEL); return TRUE; }
    return FALSE;
}

static int EnginePaths(void)
{
    DWORD n = GetModuleFileNameW(NULL, module_path, 32768);
    if (!n || n >= 32768) return 0;
    while (n && module_path[n - 1] != L'\\') --n;
    if (!n) return 0;
    module_path[n] = 0;
    return Copy(engine_directory, 32768, module_path) &&
           Append(engine_directory, 32768, MASTIXA_PAYLOAD_DIRECTORY) &&
           Copy(engine_path, 32768, engine_directory) &&
           Append(engine_path, 32768, L"\\MastixaManager.exe");
}

static DWORD LaunchEngine(BOOL *started)
{
    WCHAR **argv, *command;
    MastixaChild child;
    DWORD result, error;
    int argc, i, valid;
    unsigned int used = 0;
    *started = FALSE;
    if (!EnginePaths()) return ERROR_BAD_PATHNAME;
    argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) return GetLastError();
    command = (WCHAR *)HeapAlloc(GetProcessHeap(), 0, 32768 * sizeof(WCHAR));
    if (!command) { LocalFree(argv); return ERROR_NOT_ENOUGH_MEMORY; }
    command[0] = 0;
    valid = VcQuote(command, 32768, &used, engine_path);
    for (i = 1; valid && i < argc; ++i)
        valid = VcPut(command, 32768, &used, L' ') && VcQuote(command, 32768, &used, argv[i]);
    LocalFree(argv);
    if (!valid) { HeapFree(GetProcessHeap(), 0, command); return ERROR_BAD_LENGTH; }
    /* Exact application name, deterministic program working directory, no shell,
       no executable from PATH/CWD and no inherited handles. Arguments survive. */
    if (!MastixaStartChild(&child, engine_path, command, engine_directory)) {
        error = GetLastError();
        HeapFree(GetProcessHeap(), 0, command);
        return error;
    }
    HeapFree(GetProcessHeap(), 0, command);
    *started = TRUE;
    if (WaitForSingleObject(child.process.hProcess, INFINITE) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(child.process.hProcess, &result)) result = ERROR_GEN_FAILURE;
    /* Normal application exit must not kill its separately requested updater. */
    if (!MastixaAllowChildDescendants(&child)) result = ERROR_GEN_FAILURE;
    CloseHandle(child.process.hProcess);
    CloseHandle(child.job);
    return result;
}

static DWORD RunLauncher(void)
{
    DWORD result;
    BOOL started;
    last_result = ProbeRuntime();
    if (last_result != VC_READY &&
        DialogBoxParamW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(IDD_PREREQUISITE), NULL,
                        PrerequisiteDialog, 0) != IDOK) return ERROR_CANCELLED;
    result = LaunchEngine(&started);
    if (!started) {
        MessageBoxW(NULL, L"Δεν ήταν δυνατή η εκκίνηση του Mastixa Manager. "
                    L"Εκτελέστε ξανά την εγκατάσταση για επιδιόρθωση των αρχείων εφαρμογής. "
                    L"Τα δεδομένα σας διατηρούνται.", L"Mastixa Manager", MB_OK | MB_ICONERROR);
    } else if (result == 0xc0000135 || result == 0xc000007b || result == 0xc0000142) {
        MessageBoxW(NULL, L"Η εφαρμογή δεν ξεκίνησε λόγω προβλήματος σε βιβλιοθήκη Windows. "
                    L"Ελέγξτε το επίσημο Visual C++ x64 και επιδιορθώστε την εγκατάσταση Mastixa Manager. "
                    L"Τα δεδομένα σας διατηρούνται.", L"Mastixa Manager", MB_OK | MB_ICONERROR);
    }
    return result;
}

__declspec(safebuffers) void WINAPI MastixaLauncherEntry(void)
{
    /* No CRT startup/constructors: first-party guard initialization must precede
       every /GS-protected function. A random-source failure stops safely. */
    if (!MastixaInitializeCookie()) {
        MessageBoxW(NULL, L"Δεν ήταν δυνατή η ασφαλής εκκίνηση. Δοκιμάστε ξανά ή "
                    L"επιδιορθώστε την εγκατάσταση Mastixa Manager.", L"Mastixa Manager", MB_OK | MB_ICONERROR);
        ExitProcess(ERROR_GEN_FAILURE);
    }
    ExitProcess(RunLauncher());
}
