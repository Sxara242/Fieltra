/* SPDX-License-Identifier: AGPL-3.0-only
 * First-party /GS support: no Microsoft CRT object/library is linked.
 * Entry points initialize a random cookie before calling /GS-protected code.
 */
#include <windows.h>
#include <bcrypt.h>
#include <intrin.h>
#include <excpt.h>
ULONG_PTR __security_cookie = 0x2b992ddfa232;
ULONG_PTR __security_cookie_complement;
/* Give the Windows loader/linker a real load-config directory for the cookie
   and System32-only dependent-load flags, rather than silently losing hardening. */
const IMAGE_LOAD_CONFIG_DIRECTORY64 _load_config_used = {
    .Size = sizeof(IMAGE_LOAD_CONFIG_DIRECTORY64),
    .SecurityCookie = (ULONGLONG)&__security_cookie
};

__declspec(safebuffers) void __cdecl __security_check_cookie(ULONG_PTR cookie)
{
    if (cookie != __security_cookie) __fastfail(FAST_FAIL_STACK_COOKIE_CHECK_FAILURE);
}
__declspec(safebuffers) __declspec(noreturn) void __cdecl __report_rangecheckfailure(void)
{
    __fastfail(FAST_FAIL_RANGE_CHECK_FAILURE);
}
/* No recoverable SEH/C++ handlers exist in the launcher. If Windows tries to
   unwind a /GS-protected frame after an exception, terminate immediately;
   never emulate an undocumented CRT unwinding/cookie implementation. Ordinary
   Win32 failures still use their checked return values and friendly dialog. */
__declspec(safebuffers) EXCEPTION_DISPOSITION __cdecl __GSHandlerCheck(
    PEXCEPTION_RECORD exception, ULONG64 frame, PCONTEXT context, PDISPATCHER_CONTEXT dispatcher)
{
    (void)exception; (void)frame; (void)context; (void)dispatcher;
    __fastfail(FAST_FAIL_FATAL_APP_EXIT);
    return ExceptionContinueSearch; /* unreachable after int 0x29; typed dispatcher ABI */
}
__declspec(safebuffers) int MastixaInitializeCookie(void)
{
    ULONG_PTR value;
    if (BCryptGenRandom(NULL, (PUCHAR)&value, sizeof(value), BCRYPT_USE_SYSTEM_PREFERRED_RNG) < 0)
        return 0;
    value &= 0x0000ffffffffffff;
    if (!value || value == __security_cookie) value ^= 0x4711;
    __security_cookie = value;
    __security_cookie_complement = ~value;
    return 1;
}
