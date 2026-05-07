# Security Review Checklist

This document provides a comprehensive security checklist for code reviews.

## Authentication & Authorization

### Authentication
- [ ] Are authentication tokens validated properly?
- [ ] Is session management secure (timeouts, revocation)?
- [ ] Are credentials never stored in plain text?
- [ ] Is multi-factor authentication supported where needed?
- [ ] Are password requirements enforced (complexity, length)?
- [ ] Is there protection against brute force attacks?
- [ ] Are authentication failures logged?

### Authorization
- [ ] Are all endpoints protected with proper authorization checks?
- [ ] Is role-based access control (RBAC) properly implemented?
- [ ] Are users only able to access their own data?
- [ ] Is there proper validation of user permissions before operations?
- [ ] Are there no authorization bypasses through direct object references?
- [ ] Is the principle of least privilege followed?

## Input Validation & Sanitization

### General Input Validation
- [ ] Are all user inputs validated for type, format, and range?
- [ ] Is input validation performed on the server side (not just client)?
- [ ] Are file uploads validated for type, size, and content?
- [ ] Are uploaded files stored outside the web root?
- [ ] Is there validation of HTTP headers and parameters?

### Injection Prevention
- [ ] **SQL Injection**: Are parameterized queries/ORMs used for all database operations?
- [ ] **NoSQL Injection**: Are NoSQL queries properly sanitized?
- [ ] **Command Injection**: Is shell command execution avoided? If necessary, are inputs sanitized?
- [ ] **LDAP Injection**: Are LDAP queries properly escaped?
- [ ] **XPath Injection**: Are XPath queries parameterized?
- [ ] **Template Injection**: Are template engines configured securely?

### Cross-Site Scripting (XSS)
- [ ] Is all user-generated content properly escaped before rendering?
- [ ] Are Content Security Policy (CSP) headers configured?
- [ ] Is HTML sanitization used for rich text inputs?
- [ ] Are JavaScript contexts properly escaped?
- [ ] Are URL parameters escaped when reflected in responses?
- [ ] Is output encoding context-aware (HTML, JavaScript, URL, CSS)?

## Data Protection

### Sensitive Data
- [ ] Is sensitive data encrypted at rest?
- [ ] Is sensitive data encrypted in transit (HTTPS/TLS)?
- [ ] Are passwords hashed with strong algorithms (bcrypt, Argon2)?
- [ ] Is personally identifiable information (PII) minimized?
- [ ] Are API keys and secrets stored in secure vaults (not in code)?
- [ ] Is sensitive data masked in logs and error messages?
- [ ] Are database backups encrypted?

### Data Exposure
- [ ] Are error messages generic (not revealing system details)?
- [ ] Is sensitive data excluded from URLs and logs?
- [ ] Are API responses not leaking unnecessary information?
- [ ] Is there no sensitive data in client-side code or comments?
- [ ] Are debug/verbose modes disabled in production?

## Session Management

- [ ] Are session tokens generated using cryptographically secure random generators?
- [ ] Are session tokens invalidated on logout?
- [ ] Do sessions expire after appropriate timeout?
- [ ] Are session tokens transmitted only over HTTPS?
- [ ] Are session cookies marked as HttpOnly and Secure?
- [ ] Is SameSite cookie attribute set appropriately?
- [ ] Are concurrent sessions handled properly?

## Cross-Site Request Forgery (CSRF)

- [ ] Are CSRF tokens implemented for state-changing operations?
- [ ] Are CSRF tokens validated on the server side?
- [ ] Are CSRF tokens tied to user sessions?
- [ ] Is SameSite cookie attribute used as additional protection?
- [ ] Are GET requests never used for state-changing operations?

## API Security

### API Authentication
- [ ] Are API keys transmitted securely (not in URLs)?
- [ ] Is API key rotation supported?
- [ ] Are API authentication errors handled without information leakage?
- [ ] Is OAuth/JWT implemented correctly if used?
- [ ] Are refresh tokens stored securely?

### API Rate Limiting
- [ ] Is rate limiting implemented for API endpoints?
- [ ] Are rate limits appropriate for the operation sensitivity?
- [ ] Is rate limiting enforced per user/IP?
- [ ] Are rate limit errors handled gracefully?

### API Data Validation
- [ ] Is request body size limited?
- [ ] Are JSON/XML payloads validated against schemas?
- [ ] Is there protection against parameter pollution?
- [ ] Are content types validated?

## Cryptography

- [ ] Are only strong, modern cryptographic algorithms used?
- [ ] Are cryptographic keys of sufficient length?
- [ ] Is encryption properly initialized with secure random IVs/nonces?
- [ ] Are cryptographic libraries used correctly (not custom crypto)?
- [ ] Is TLS 1.2+ used (1.0 and 1.1 disabled)?
- [ ] Are certificate validations not bypassed?
- [ ] Are weak cipher suites disabled?

## File Operations

### File Uploads
- [ ] Are file types validated by content (not just extension)?
- [ ] Are uploaded files scanned for malware?
- [ ] Are uploaded file names sanitized?
- [ ] Is there a maximum file size limit?
- [ ] Are uploaded files stored with random names?
- [ ] Are uploaded files not directly executable?

### File Downloads
- [ ] Is there no path traversal vulnerability (../)?
- [ ] Are file downloads authenticated and authorized?
- [ ] Are content-type headers set correctly?
- [ ] Is there protection against directory listing?

## Error Handling & Logging

### Error Handling
- [ ] Are exceptions caught and handled properly?
- [ ] Do error messages not reveal sensitive information?
- [ ] Are stack traces not shown to users in production?
- [ ] Are errors logged for security monitoring?

### Logging
- [ ] Are security events logged (authentication failures, authorization violations)?
- [ ] Are logs protected from unauthorized access?
- [ ] Do logs not contain sensitive data (passwords, tokens)?
- [ ] Is there log rotation and retention policy?
- [ ] Are logs monitored for suspicious activity?

## Third-Party Dependencies

- [ ] Are all dependencies from trusted sources?
- [ ] Are dependencies scanned for known vulnerabilities?
- [ ] Are dependencies kept up to date?
- [ ] Are dependency versions pinned?
- [ ] Are unused dependencies removed?
- [ ] Is there a process for security updates?

## Configuration & Deployment

- [ ] Are default credentials changed?
- [ ] Are unnecessary services and ports disabled?
- [ ] Is debug mode disabled in production?
- [ ] Are security headers configured (HSTS, X-Frame-Options, etc.)?
- [ ] Is directory indexing disabled?
- [ ] Are source control files (.git, .env) not accessible?
- [ ] Is there no sensitive information in environment variables visible to users?

## Common Vulnerability Patterns

### OWASP Top 10 Checks
1. **Broken Access Control**: Verify authorization checks at every level
2. **Cryptographic Failures**: Ensure proper encryption of sensitive data
3. **Injection**: Validate and sanitize all inputs
4. **Insecure Design**: Review architecture for security considerations
5. **Security Misconfiguration**: Check for secure defaults and configurations
6. **Vulnerable Components**: Verify dependencies are up to date
7. **Identification and Authentication Failures**: Ensure proper auth implementation
8. **Software and Data Integrity Failures**: Verify code and data integrity
9. **Security Logging and Monitoring Failures**: Ensure adequate logging
10. **Server-Side Request Forgery (SSRF)**: Validate and restrict outbound requests

## Language-Specific Security Considerations

### Python
- [ ] Is user input not used in `eval()` or `exec()`?
- [ ] Is `pickle` not used with untrusted data?
- [ ] Are SQL queries using parameterized statements?
- [ ] Is `subprocess` used with `shell=False`?

### JavaScript/Node.js
- [ ] Is `eval()` avoided?
- [ ] Are packages from npm verified and scanned?
- [ ] Is there no XSS in template rendering?
- [ ] Are environment variables not exposed to client?

### Java
- [ ] Is deserialization of untrusted data avoided?
- [ ] Are prepared statements used for SQL?
- [ ] Is XXE (XML External Entity) protection enabled?
- [ ] Are security managers configured properly?

### Go
- [ ] Are SQL queries parameterized?
- [ ] Is HTML template auto-escaping enabled?
- [ ] Are goroutines protected from panics?
- [ ] Is crypto/rand used (not math/rand for security)?

## Red Flags to Watch For

🚩 **Immediate Security Concerns:**
- String concatenation in SQL queries
- User input in shell commands
- Disabled SSL certificate validation
- Hardcoded credentials or API keys
- `eval()` or `exec()` with user input
- Deserialization of untrusted data
- Missing authentication on sensitive endpoints
- Direct file path access from user input
- Weak cryptographic algorithms (MD5, SHA1 for passwords)
- Storing passwords in plain text or reversible encryption

## Review Example

```python
# ❌ INSECURE
def login(username, password):
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    user = db.execute(query)
    if user:
        session['user_id'] = user.id
        return redirect('/dashboard')

# ✅ SECURE
def login(username, password):
    # Use parameterized query
    query = "SELECT * FROM users WHERE username = %s"
    user = db.execute(query, (username,))

    if not user:
        logger.warning(f"Failed login attempt for username: {username}")
        return render_template('login.html', error="Invalid credentials")

    # Verify password using secure hash comparison
    if not bcrypt.checkpw(password.encode(), user.password_hash):
        logger.warning(f"Failed login attempt for user_id: {user.id}")
        return render_template('login.html', error="Invalid credentials")

    # Set secure session
    session.regenerate()
    session['user_id'] = user.id
    session['authenticated'] = True

    logger.info(f"Successful login for user_id: {user.id}")
    return redirect('/dashboard')
```

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [SANS Top 25](https://www.sans.org/top25-software-errors/)
