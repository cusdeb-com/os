#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "../../src/dll/win32/shlwapi/sxsactctx.h"

static const GUID clsid = {0x03c036f1, 0xa186, 0x11d0, {0x82, 0x4a, 0, 0xaa, 0, 0x5b, 0x43, 0x83}};
static const GUID alias = {0xdeadbeef, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 1, 2, 3, 4}};
static const GUID unknown = {0xdeadbeee, 0x1234, 0x5678, {0x90, 0xab, 0xcd, 0xef, 1, 2, 3, 4}};

struct fixture
{
    ACTCTX_SECTION_KEYED_DATA data;
    BYTE section[512];
};

static unsigned int checks;
static unsigned int failures;

static void check(const char *name, DWORD actual, DWORD expected)
{
    ++checks;
    if (actual == expected)
        printf("PASS: %s\n", name);
    else
    {
        printf("FAIL: %s (got %lu, expected %lu)\n", name, actual, expected);
        ++failures;
    }
}

static struct shpin_comclassredirect_data *setup(struct fixture *fixture)
{
    static const WCHAR provider[] = L"browseui.dll";
    struct shpin_comclassredirect_data *redirect;

    memset(fixture, 0, sizeof(*fixture));
    fixture->data.cbSize = sizeof(fixture->data);
    fixture->data.ulDataFormatVersion = 1;
    fixture->data.lpSectionBase = fixture->section;
    fixture->data.ulSectionTotalLength = sizeof(*redirect) + sizeof(provider);
    fixture->data.ulAssemblyRosterIndex = 1;
    fixture->data.lpData = fixture->section;
    fixture->data.ulLength = sizeof(*redirect);

    redirect = (struct shpin_comclassredirect_data *)fixture->section;
    redirect->size = sizeof(*redirect);
    redirect->clsid = clsid;
    redirect->alias = alias;
    redirect->name_len = sizeof(provider) - sizeof(WCHAR);
    redirect->name_offset = sizeof(*redirect);
    memcpy(fixture->section + redirect->name_offset, provider, sizeof(provider));
    return redirect;
}

int main(void)
{
    struct fixture fixture;
    struct shpin_comclassredirect_data *redirect = setup(&fixture);
    LPCWSTR provider = NULL;
    DWORD error;

    error = SHPinParseActCtxComServer(&fixture.data, &clsid, &provider);
    check("valid provider record", error, ERROR_SUCCESS);
    check("provider filename", provider && !lstrcmpW(provider, L"browseui.dll"), TRUE);

    error = SHPinParseActCtxComServer(&fixture.data, &alias, &provider);
    check("ProgID alias resolves to the same provider", error, ERROR_SUCCESS);

    check("nonmatching CLSID rejected",
          SHPinParseActCtxComServer(&fixture.data, &unknown, &provider), ERROR_INVALID_DATA);
    check("failed parse clears provider output", provider == NULL, TRUE);

    setup(&fixture);
    fixture.data.ulDataFormatVersion = 2;
    check("unknown section format rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_REVISION_MISMATCH);

    setup(&fixture);
    fixture.data.cbSize = FIELD_OFFSET(ACTCTX_SECTION_KEYED_DATA, ulAssemblyRosterIndex);
    provider = (LPCWSTR)1;
    check("truncated keyed data rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_PARAMETER);
    check("truncated keyed data clears output", provider == NULL, TRUE);

    setup(&fixture);
    fixture.data.ulAssemblyRosterIndex = 0;
    check("zero assembly roster rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    setup(&fixture);
    fixture.data.ulLength--;
    check("truncated COM record rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    setup(&fixture);
    fixture.data.lpData = fixture.section + sizeof(fixture.section) - 1;
    check("record pointer outside section rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    setup(&fixture);
    fixture.data.lpData = fixture.section + 1;
    check("unaligned record pointer rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    redirect->name_offset = ~(ULONG)0;
    check("overflowing name offset rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    redirect->name_len--;
    check("odd UTF-16 byte length rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    redirect->clrdata_len = 1;
    check("unsupported CLR registration rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_NOT_SUPPORTED);

    redirect = setup(&fixture);
    ((WCHAR *)(fixture.section + redirect->name_offset))[0] = 0;
    check("embedded NUL rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    ((WCHAR *)(fixture.section + redirect->name_offset))[0] = 0xd800;
    check("unpaired UTF-16 surrogate rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    ((WCHAR *)(fixture.section + redirect->name_offset))[lstrlenW(L"browseui.dll")] = L'x';
    check("missing UTF-16 terminator rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    redirect = setup(&fixture);
    redirect->size = sizeof(*redirect) + 1;
    check("oversized record rejected", SHPinParseActCtxComServer(&fixture.data, &clsid, &provider),
          ERROR_INVALID_DATA);

    printf("Parser result: %s (%u checks, %u failures)\n",
           failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
