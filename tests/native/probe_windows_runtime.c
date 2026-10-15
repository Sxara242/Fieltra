/* SPDX-License-Identifier: AGPL-3.0-only
 * Read-only console diagnostics using the EXACT production detection code.
 * The selected entry point never calls RunLauncher/LaunchEngine/a dialog.
 * This tool is not installed or distributed with Mastixa Manager.
 */
#include "../../packaging/windows_launcher/launcher.c"
__declspec(safebuffers) void WINAPI MastixaRuntimeProbeEntry(void)
{
    DWORD written;
    enum VcResult result;
    char number;
    static const char label[] = "Read-only production probe: 0=ready, 1=missing, 2=outdated, 3=wrong architecture, 4=check error; result=";
    if (!MastixaInitializeCookie()) ExitProcess(99);
    result = ProbeRuntime();
    number = (char)('0' + result);
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), label, sizeof(label) - 1, &written, NULL);
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), &number, 1, &written, NULL);
    WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), "\r\n", 2, &written, NULL);
    ExitProcess(result);
}
