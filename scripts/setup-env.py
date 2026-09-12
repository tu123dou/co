"""本地配置脚本：首次创建 .env，并保护用户已经填写的配置和密钥。"""

from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
p = root / ".env"
if p.exists():
    print(".env already exists; preserved.")
else:
    template = (root / ".env.example").read_text()
    for key in [
        "APP_DB_PASSWORD",
        "QUERY_DB_PASSWORD",
        "POSTGRES_PASSWORD",
        "JWT_SECRET",
        "ADMIN_PASSWORD",
    ]:
        template = template.replace("${" + key + "}", secrets.token_urlsafe(24))
    # Expand URL references only after generating stable per-key secrets.
    env = dict(
        line.split("=", 1)
        for line in template.splitlines()
        if "=" in line and not line.startswith("#")
    )
    for key, value in env.items():
        template = template.replace("${" + key + "}", value)
    p.write_text(template)
    p.chmod(0o600)
    print(
        "Created .env. Configure LLM_API_KEY and use ADMIN_PASSWORD to log in as admin."
    )
