/* SPDX-License-Identifier: AGPL-3.0-only
 * Bounded Windows argv quoting, including quotes and trailing backslashes.
 */
#ifndef MASTIXA_ARGUMENTS_H
#define MASTIXA_ARGUMENTS_H
static int VcPut(wchar_t *out, unsigned int capacity, unsigned int *used, wchar_t c)
{
    if (*used + 1 >= capacity) return 0;
    out[(*used)++] = c;
    out[*used] = 0;
    return 1;
}
static int VcQuote(wchar_t *out, unsigned int capacity, unsigned int *used, const wchar_t *arg)
{
    unsigned int slashes, i;
    if (!VcPut(out, capacity, used, L'"')) return 0;
    for (;;) {
        slashes = 0;
        while (*arg == L'\\') { ++slashes; ++arg; }
        if (!*arg || *arg == L'"') slashes *= 2;
        for (i = 0; i < slashes; ++i) if (!VcPut(out, capacity, used, L'\\')) return 0;
        if (!*arg) break;
        if (*arg == L'"' && !VcPut(out, capacity, used, L'\\')) return 0;
        if (!VcPut(out, capacity, used, *arg++)) return 0;
    }
    return VcPut(out, capacity, used, L'"');
}
#endif
