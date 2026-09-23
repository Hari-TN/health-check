{
    "name":          "BOP Transfer List",     # ← shown in email
    "auth_url":      "https://..../login",    # ← auth endpoint
    "auth_method":   "POST",                  # ← POST or GET
    "auth_body":     {"userName": "admin",    # ← credentials
                      "password": "jwt123"},
    "token_field":   "code",                  # ← key in auth response
    "check_url":     "https://..../transfer", # ← health check endpoint
    "check_method":  "GET",                   # ← GET or POST
    "success_path":  "status.code",           # ← dot path to check
    "success_value": "000000",                # ← expected value
},
