# CWE-798: Use of Hard-coded Credentials

## Metadata
- ID: CWE-798
- Category: secrets
- Severity: HIGH to CRITICAL
- CVSS: 7.5 - 9.8

## Description
The software contains hard-coded credentials, such as a password or cryptographic key, which it uses for authentication or encryption of data.

## Why It's Dangerous
- Credentials in source code can be extracted by anyone with access to the code
- Often leaked through version control (GitHub, GitLab)
- Cannot be rotated without code changes and redeployment
- Same credentials often used across environments (dev, staging, prod)

## Vulnerable Patterns in Python

### Hardcoded Passwords
```python
# VULNERABLE
DB_PASSWORD = "supersecret123"
ADMIN_PASSWORD = "admin123"

def connect_db():
    return psycopg2.connect(
        host="localhost",
        password="mysecretpassword"  # Hardcoded!
    )
```

### Hardcoded API Keys
```python
# VULNERABLE - API keys in source
API_KEY = "sk-1234567890abcdef1234567890abcdef"
STRIPE_SECRET = "sk_live_1234567890abcdef"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

### Hardcoded JWT Secrets
```python
# VULNERABLE
JWT_SECRET = "my-super-secret-jwt-key"

def create_token(user_id):
    return jwt.encode(
        {"user_id": user_id},
        "hardcoded-secret",  # Hardcoded!
        algorithm="HS256"
    )
```

### Connection Strings with Credentials
```python
# VULNERABLE
DATABASE_URL = "postgresql://admin:password123@localhost/mydb"
REDIS_URL = "redis://:secretpass@localhost:6379/0"
MONGODB_URI = "mongodb://user:pass@localhost:27017/db"
```

## Secure Alternatives

### Environment Variables
```python
# SECURE - Use environment variables
import os

DB_PASSWORD = os.environ.get("DB_PASSWORD")
API_KEY = os.environ.get("API_KEY")

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD environment variable required")
```

### Configuration Files (Not in Git)
```python
# SECURE - Load from .env file (not committed)
from dotenv import load_dotenv
import os

load_dotenv()  # Loads from .env file

DB_PASSWORD = os.getenv("DB_PASSWORD")
API_KEY = os.getenv("API_KEY")
```

### Secrets Managers
```python
# SECURE - AWS Secrets Manager
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# SECURE - HashiCorp Vault
import hvac

client = hvac.Client(url='https://vault.example.com')
secret = client.secrets.kv.v2.read_secret_version(path='myapp/db')
DB_PASSWORD = secret['data']['data']['password']
```

### Azure Key Vault
```python
# SECURE - Azure Key Vault
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net/", credential=credential)
secret = client.get_secret("db-password")
DB_PASSWORD = secret.value
```

## Detection Patterns
```python
# Regex patterns for detection
HARDCODED_PATTERNS = [
    r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']',
    r'(?i)(api[_-]?key|apikey)\s*=\s*["\'][^"\']+["\']',
    r'(?i)(secret|token)\s*=\s*["\'][^"\']+["\']',
    r'(?i)AWS_ACCESS_KEY.*=.*["\'][A-Z0-9]{20}["\']',
    r'(?i)AWS_SECRET.*=.*["\'][A-Za-z0-9/+=]{40}["\']',
    r'sk-[a-zA-Z0-9]{32,}',  # OpenAI API key
    r'sk_live_[a-zA-Z0-9]{24,}',  # Stripe live key
    r'AKIA[A-Z0-9]{16}',  # AWS Access Key ID
    r'ghp_[a-zA-Z0-9]{36}',  # GitHub Personal Access Token
]
```

## Best Practices
1. **Never commit secrets** - Use .gitignore for .env files
2. **Use environment variables** - Inject at runtime
3. **Use secrets managers** - AWS/Azure/GCP/Vault
4. **Rotate regularly** - Automate rotation
5. **Scan for leaks** - Use tools like gitleaks, truffleHog
6. **Principle of least privilege** - Limit scope of credentials

## References
- https://cwe.mitre.org/data/definitions/798.html
- https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password
