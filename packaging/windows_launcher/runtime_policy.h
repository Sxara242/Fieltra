/* SPDX-License-Identifier: AGPL-3.0-only
 * Pure policy, shared by the launcher and a native synthetic test executable.
 * No registry, file, GUI or process operations occur in this header.
 */
#ifndef MASTIXA_RUNTIME_POLICY_H
#define MASTIXA_RUNTIME_POLICY_H
#include "policy_config.h"

typedef struct { unsigned int part[4]; } VcVersion;
enum VcSampleState { VC_ABSENT, VC_VALID, VC_INVALID, VC_ACCESS_ERROR };
typedef struct {
    enum VcSampleState state;
    VcVersion version;
    unsigned int machine;
} VcSample;
typedef struct {
    VcSample registry[2]; /* HKLM x64 subkey, explicitly 64- and 32-bit views */
    VcSample files[MASTIXA_DLL_COUNT]; /* canonical System32 files only */
} VcProbe;
enum VcResult { VC_READY, VC_MISSING, VC_OUTDATED, VC_WRONG_ARCH, VC_CHECK_ERROR };

static int VcVersionAtLeast(VcVersion version)
{
    const unsigned int minimum[4] = {
        MASTIXA_MIN_MAJOR, MASTIXA_MIN_MINOR, MASTIXA_MIN_BUILD, MASTIXA_MIN_REVISION
    };
    unsigned int i;
    for (i = 0; i < 4; ++i) {
        if (version.part[i] != minimum[i]) return version.part[i] > minimum[i];
    }
    return 1;
}

static enum VcResult VcEvaluate(const VcProbe *probe)
{
    unsigned int i;
    int registry_ready = 0, outdated = 0, error = 0;
    for (i = 0; i < 2; ++i) {
        if (probe->registry[i].state == VC_VALID) {
            if (VcVersionAtLeast(probe->registry[i].version)) registry_ready = 1;
            else outdated = 1;
        } else if (probe->registry[i].state != VC_ABSENT) error = 1;
    }
    if (!registry_ready) return error ? VC_CHECK_ERROR : (outdated ? VC_OUTDATED : VC_MISSING);
    for (i = 0; i < MASTIXA_DLL_COUNT; ++i) {
        const VcSample *file = &probe->files[i];
        if (file->state == VC_ABSENT) return VC_MISSING;
        if (file->state != VC_VALID) return VC_CHECK_ERROR;
        if (file->machine != 0x8664) return VC_WRONG_ARCH;
        if (!VcVersionAtLeast(file->version)) return VC_OUTDATED;
    }
    return VC_READY;
}
#endif
