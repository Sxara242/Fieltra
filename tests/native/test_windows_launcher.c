/* SPDX-License-Identifier: AGPL-3.0-only
 * Headless synthetic policy/argv/owned-child tests. Child processes are ONLY
 * this fixture in sleep mode. Never reads registry, runs a real app payload,
 * displays a dialog, accesses Mastixa data or installs a component.
 */
#include <windows.h>
#include <shellapi.h>
#include "runtime_policy.h"
#include "arguments.h"
#include "job_child.h"
int MastixaInitializeCookie(void);
static unsigned int failures, checks;
static void Check(int condition)
{
    ++checks;
    if (!condition) ++failures;
}
static void Ready(VcProbe *probe)
{
    unsigned int i, j;
    volatile BYTE *clear = (volatile BYTE *)probe;
    for (i = 0; i < sizeof(*probe); ++i) clear[i] = 0;
    probe->registry[0].state = VC_VALID;
    probe->registry[0].version.part[0] = MASTIXA_MIN_MAJOR;
    probe->registry[0].version.part[1] = MASTIXA_MIN_MINOR;
    probe->registry[0].version.part[2] = MASTIXA_MIN_BUILD;
    probe->registry[0].version.part[3] = MASTIXA_MIN_REVISION;
    for (i = 0; i < MASTIXA_DLL_COUNT; ++i) {
        probe->files[i].state = VC_VALID;
        probe->files[i].machine = 0x8664;
        for (j = 0; j < 4; ++j) probe->files[i].version.part[j] = probe->registry[0].version.part[j];
    }
}
static int Equal(const WCHAR *a, const WCHAR *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static void RunTests(void)
{
    VcProbe probe;
    unsigned int i, used;
    WCHAR command[512];
    WCHAR **parsed;
    int count;
    static const WCHAR *const arguments[] = {
        L"C:\\Program Files\\Mastixa Manager\\engine\\MastixaManager.exe",
        L"", L"--smoke-test", L"Ελληνικά με κενά", L"trailing\\", L"quotes\"inside",
        L"slashes\\\\\"quote", L"& whoami > ignored.txt"
    };
    Ready(&probe); Check(VcEvaluate(&probe) == VC_READY);
    probe.registry[0].state = VC_ABSENT; Check(VcEvaluate(&probe) == VC_MISSING);
    probe.registry[0].state = VC_ACCESS_ERROR; Check(VcEvaluate(&probe) == VC_CHECK_ERROR);
    probe.registry[0].state = VC_INVALID; Check(VcEvaluate(&probe) == VC_CHECK_ERROR);
    Ready(&probe); probe.registry[0].version.part[2]--; Check(VcEvaluate(&probe) == VC_OUTDATED);
    Ready(&probe); probe.registry[1] = probe.registry[0]; probe.registry[0].state = VC_ACCESS_ERROR;
    Check(VcEvaluate(&probe) == VC_READY); /* positive other view + all real file samples */
    for (i = 0; i < MASTIXA_DLL_COUNT; ++i) {
        Ready(&probe); probe.files[i].state = VC_ABSENT; Check(VcEvaluate(&probe) == VC_MISSING);
        Ready(&probe); probe.files[i].state = VC_ACCESS_ERROR; Check(VcEvaluate(&probe) == VC_CHECK_ERROR);
        Ready(&probe); probe.files[i].state = VC_INVALID; Check(VcEvaluate(&probe) == VC_CHECK_ERROR);
        Ready(&probe); probe.files[i].machine = 0x14c; Check(VcEvaluate(&probe) == VC_WRONG_ARCH);
        Ready(&probe); probe.files[i].version.part[2]--; Check(VcEvaluate(&probe) == VC_OUTDATED);
    }
    Ready(&probe); probe.registry[0].version.part[1]++; Check(VcEvaluate(&probe) == VC_READY);
    Ready(&probe); probe.registry[0].version.part[0]--; probe.registry[0].version.part[1] = 65535;
    Check(VcEvaluate(&probe) == VC_OUTDATED);
    Ready(&probe); probe.registry[0].version.part[3]++; Check(VcEvaluate(&probe) == VC_READY);
    used = 0; command[0] = 0;
    for (i = 0; i < sizeof(arguments) / sizeof(arguments[0]); ++i) {
        if (i) Check(VcPut(command, 512, &used, L' '));
        Check(VcQuote(command, 512, &used, arguments[i]));
    }
    parsed = CommandLineToArgvW(command, &count);
    Check(parsed != NULL && count == (int)(sizeof(arguments) / sizeof(arguments[0])));
    if (parsed && count == (int)(sizeof(arguments) / sizeof(arguments[0])))
        for (i = 0; i < (unsigned int)count; ++i) Check(Equal(parsed[i], arguments[i]));
    if (parsed) LocalFree(parsed);
    used = 0; command[0] = 0; Check(!VcQuote(command, 4, &used, L"too long"));
}
static void TestChildLifetime(void)
{
    WCHAR path[512], command[1024];
    unsigned int used = 0;
    DWORD code;
    BOOL started;
    MastixaChild child;
    Check(GetModuleFileNameW(NULL, path, 512) > 0);
    command[0] = 0;
    Check(VcQuote(command, 1024, &used, path));
    Check(VcPut(command, 1024, &used, L' '));
    Check(VcQuote(command, 1024, &used, L"--mastixa-synthetic-child"));
    started = MastixaStartChild(&child, path, command, NULL);
    Check(started);
    if (started) {
        CloseHandle(child.job); /* simulates forced parent/job-handle closure */
        Check(WaitForSingleObject(child.process.hProcess, 5000) == WAIT_OBJECT_0);
        Check(GetExitCodeProcess(child.process.hProcess, &code) && code != STILL_ACTIVE);
        CloseHandle(child.process.hProcess);
    }
    used = 0; command[0] = 0;
    Check(VcQuote(command, 1024, &used, path));
    Check(VcPut(command, 1024, &used, L' '));
    Check(VcQuote(command, 1024, &used, L"--mastixa-synthetic-child"));
    started = MastixaStartChild(&child, path, command, NULL);
    Check(started);
    if (started) {
        Check(MastixaAllowChildDescendants(&child));
        CloseHandle(child.job); /* normal detach must keep an updater child alive */
        Check(WaitForSingleObject(child.process.hProcess, 0) == WAIT_TIMEOUT);
        Check(WaitForSingleObject(child.process.hProcess, 5000) == WAIT_OBJECT_0);
        Check(GetExitCodeProcess(child.process.hProcess, &code) && code == 0);
        CloseHandle(child.process.hProcess);
    }
}
static void ReportCount(void)
{
    char digits[16];
    unsigned int n = checks, count = 0, i;
    DWORD written;
    static const char label[] = "Native assertion count: ";
    do { digits[count++] = (char)('0' + n % 10); n /= 10; } while (n);
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), label, sizeof(label) - 1, &written, NULL);
    for (i = count; i; --i) WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), &digits[i - 1], 1, &written, NULL);
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), "\r\n", 2, &written, NULL);
}
__declspec(safebuffers) void WINAPI MastixaTestEntry(void)
{
    DWORD written;
    WCHAR **args;
    int count;
    static const char pass[] = "PASS: synthetic runtime policy, Windows argv round-trip and owned fixture child lifetimes; no registry/UI/real payload operations.\r\n";
    static const char fail[] = "FAIL: native synthetic policy/argument assertions.\r\n";
    if (!MastixaInitializeCookie()) ExitProcess(99);
    args = CommandLineToArgvW(GetCommandLineW(), &count);
    if (args && count == 2 && Equal(args[1], L"--mastixa-synthetic-child")) {
        LocalFree(args);
        Sleep(1500);
        ExitProcess(0);
    }
    if (args) LocalFree(args);
    RunTests();
    TestChildLifetime();
    ReportCount();
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), failures ? fail : pass,
              (DWORD)(failures ? sizeof(fail) - 1 : sizeof(pass) - 1), &written, NULL);
    ExitProcess(failures);
}
