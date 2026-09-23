# ============================================================
# API CONFIG — ADD ALL YOUR APIs HERE
# ============================================================

APIS = [
    {
        "name":          "BOP Country List",
        "auth_url":      "https://apiuat.bop.ps/JWTAuthService/services/auth/login",
        "auth_method":   "POST",
        "auth_body":     {
            "userName": "admin",
            "password": "jwt123"
        },
        "token_field":   "code",
        "check_url":     "https://apidev.bop.ps/api/v1/mobile-banking-eapi/countrylist?offset=0&pagination=2",
        "check_method":  "GET",
        "success_path":  "status.code",
        "success_value": "000000",
    },
    {
        "name":          "BOP Bumpkin List",
        "auth_url":      "https://apiuat.bop.ps/JWTAuthService/services/auth/login",
        "auth_method":   "POST",
        "auth_body":     {"userName": "admin", "password": "jwt123"},
        "token_field":   "code",
        "check_url":     "https://apidev.bop.ps/api/v1/mobile-banking-eapi/countrylist?offset=0&pagination=2",
        "check_method":  "GET",
        "success_path":  "status.code",
        "success_value": "000000",
    },
    # ── FAKE FAILING API — to test failure scenario ──
    {
        "name":          "BOP Fake Failing API",
        "auth_url":      "https://httpstat.us/401",
        "auth_method":   "POST",
        "auth_body":     {"userName": "wrong", "password": "wrong"},
        "token_field":   "code",
        "check_url":     "https://httpstat.us/500",
        "check_method":  "GET",
        "success_path":  "status.code",
        "success_value": "000000",
    },
]
