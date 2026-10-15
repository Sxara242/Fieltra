/* SPDX-License-Identifier: AGPL-3.0-only
 * Own the exact suspended child and its job, never find/kill by name or PID.
 * If the launcher is forcibly killed, its job closes and stops the engine.
 * Normal engine exit clears that flag so an explicitly launched updater may
 * continue. Native synthetic tests exercise both lifetime paths.
 */
#ifndef MASTIXA_JOB_CHILD_H
#define MASTIXA_JOB_CHILD_H
typedef struct { HANDLE job; PROCESS_INFORMATION process; } MastixaChild;
static void ChildClear(void *data, SIZE_T bytes)
{
    volatile BYTE *p = (volatile BYTE *)data;
    while (bytes--) *p++ = 0;
}
static BOOL MastixaStartChild(MastixaChild *child, const WCHAR *application,
                             WCHAR *command, const WCHAR *directory)
{
    STARTUPINFOW startup;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    DWORD error;
    ChildClear(child, sizeof(*child));
    ChildClear(&startup, sizeof(startup));
    ChildClear(&limits, sizeof(limits));
    startup.cb = sizeof(startup);
    child->job = CreateJobObjectW(NULL, NULL);
    if (!child->job) return FALSE;
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(child->job, JobObjectExtendedLimitInformation, &limits, sizeof(limits)))
        goto failed;
    if (!CreateProcessW(application, command, NULL, NULL, FALSE,
                        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT, NULL, directory,
                        &startup, &child->process)) goto failed;
    if (!AssignProcessToJobObject(child->job, child->process.hProcess) ||
        ResumeThread(child->process.hThread) == (DWORD)-1) goto failed;
    CloseHandle(child->process.hThread);
    child->process.hThread = NULL;
    return TRUE;
failed:
    error = GetLastError();
    if (child->process.hProcess) {
        TerminateProcess(child->process.hProcess, error);
        WaitForSingleObject(child->process.hProcess, 5000);
        CloseHandle(child->process.hProcess);
    }
    if (child->process.hThread) CloseHandle(child->process.hThread);
    CloseHandle(child->job);
    ChildClear(child, sizeof(*child));
    SetLastError(error);
    return FALSE;
}
static BOOL MastixaAllowChildDescendants(MastixaChild *child)
{
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    ChildClear(&limits, sizeof(limits));
    return SetInformationJobObject(child->job, JobObjectExtendedLimitInformation, &limits, sizeof(limits));
}
#endif
