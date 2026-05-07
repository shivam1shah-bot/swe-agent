# i18n Comment Analysis Criteria

## Core Analysis Philosophy

**IMPORTANT**: Focus on **violation resolution**, not exact solution matching.

### Solution Validity Approach

When analyzing comments:

1. **Compare Similarity**: Analyze similarity between proposed changes (from comment) and actual changes made
2. **Check Violation Status**: If the new code does NOT violate i18n rules from detection-rules.md, mark as addressed
3. **Solution Flexibility**: Accept any valid solution that resolves the i18n violation, even if different from suggested fix

### Key Principle

```
✓ CORRECT: "Does the current code resolve the i18n violation?"
✗ WRONG:   "Does the current code match the exact suggested solution?"
```

**Example:**
- **Comment suggests**: `use getCurrency(userLocale)`
- **Developer implements**: `use currencyFormatter.format(amount, locale)`
- **Analysis**: If `currencyFormatter.format()` doesn't violate i18n rules → Mark as ADDRESSED ✓
- **Reasoning**: The violation (hardcoded currency) is resolved, even though solution differs

### Multiple Valid Solutions

Many i18n violations can be fixed in different ways:
- **Hardcoded "USD"** could be fixed by: `getCurrency()`, `config.currency`, `user.preferredCurrency`, `i18n.currency()`
- **All are valid** if they don't hardcode the currency and follow best-practices.md principles
- **Mark as addressed** if ANY valid solution is used

## Reference Documentation

**CRITICAL**: Before analyzing i18n comments, load the authoritative reference documentation:

1. **Detection Rules**: `.claude/skills/review-helpers/i18n-anomaly-detection/references/detection-rules.md`
   - Comprehensive patterns for all i18n violation categories
   - Anti-pattern detection criteria
   - Importance classification guidelines

2. **Best Practices**: `.claude/skills/review-helpers/i18n-anomaly-detection/references/best-practices.md`
   - Razorpay's "Think Global, Build Once" principles
   - Correct patterns for parameterization, externalization, localization
   - Observability and testing principles

3. **Language Patterns**: `.claude/skills/review-helpers/i18n-anomaly-detection/references/language-patterns.md`
   - Language-specific detection patterns (JavaScript/TypeScript, Python, Go, Java, React, Vue, etc.)
   - Common violations and correct implementations per language

**Use these references as the ground truth** for determining whether violations are resolved (not for exact solution matching).

## Specific Analysis Categories

### 1. Currency & Payment Issues
Check against `detection-rules.md` [i18n-Currency] and [i18n-Payment]:
- Hardcoded currency codes (USD, EUR, INR) removed?
- Fixed currency symbols ($, €, ₹) replaced with i18n formatters?
- Currency formatting using locale-aware functions?
- Payment method assumptions replaced with country-aware logic?

**Valid i18n Libraries for Currency (any of these indicate violation is addressed):**
- ✅ `i18nify` / `i18nify-go` / `@razorpay/i18nify` - Razorpay's i18n library (Go, JS, etc.)
  - Example: `i18nify_go.NewCountry(code).GetCountryCurrency()[0].Symbol`
  - Example: `formatCurrency(amount, {currency: getCurrencyCode()})`
- ✅ `goutils/currency` - Go currency utilities
  - Example: `currency.Get(currencyCode)`
- ✅ `Intl.NumberFormat` - JavaScript native
  - Example: `new Intl.NumberFormat(locale, {style: 'currency', currency: code})`
- ✅ Any dynamic currency lookup from config/service (not hardcoded)

### 2. Region & Country Issues
Check against `detection-rules.md` [i18n-Region]:
- Hardcoded country codes removed?
- Country-specific business logic replaced with configurable rules?
- Using GeoSDK or similar for region-specific config?

### 3. Phone Number Issues
Check against `detection-rules.md` [i18n-Phone]:
- Hardcoded country dial codes removed?
- Phone validation using country-aware patterns?
- Using libphonenumber with country context?

### 4. DateTime & Timezone Issues
Check against `detection-rules.md` [i18n-DateTime] and [i18n-Timezone]:
- Hardcoded date formats replaced with locale-aware formatting?
- Timestamps stored in UTC and displayed localized?
- Timezone not hardcoded (e.g., "America/New_York", "IST")?

### 5. Address Issues
Check against `detection-rules.md` [i18n-Address]:
- Postal code patterns country-aware?
- Address formatting using locale-specific patterns?

### 6. Language & Translation Issues
Check against `detection-rules.md` [i18n-Language]:
- Hardcoded UI text replaced with translation keys?
- User-facing strings externalized (using t(), $t(), etc.)?
- Error messages and alerts using i18n system?

### 7. Feature Flags & Experiments
Check against `detection-rules.md` [i18n-FeatureFlags]:
- Feature flags country-aware?
- Experiment frameworks include geographic context?
- Rollout strategies consider regional factors?

### 8. Best Practices Compliance
Check against `best-practices.md` principles:
- **Parameterize**: Country sourced from Account Service, not hardcoded?
- **Externalize**: Regional data in GeoSDK/i18nify/DCS, not in code?
- **Localize**: Canonical storage (UTC, minor units), localized display?
- **Fail-Safe**: Missing geo context rejected, not assumed?
- **Observe**: Country dimension in logs and metrics?

### 9. Language-Specific Patterns
Check against `language-patterns.md` for the specific language:
- JavaScript/TypeScript: Intl.NumberFormat, toLocaleDateString with locale?
- Python: pytz with user timezone, locale-aware formatting?
- Go: golang.org/x/text/message, time.Parse with locale format?
- Java: ResourceBundle, DateFormat with locale?
- React/Vue/Angular: Translation hooks/pipes properly used?

## Violation Categories

**As per detection-rules.md violation categories:**

- **`i18n-Currency`**: Hardcoded currency codes, symbols, conversion rates
- **`i18n-Region`**: Hardcoded country codes, region-specific logic
- **`i18n-Phone`**: Hardcoded phone formats, country codes, dial codes
- **`i18n-DateTime`**: Hardcoded date formats, time parsing without locale
- **`i18n-Timezone`**: Hardcoded timezone names, assumptions
- **`i18n-Address`**: Hardcoded address formats, postal code patterns
- **`i18n-Language`**: Hardcoded UI text, missing translation keys
- **`i18n-Branding`**: Hardcoded company/product names
- **`i18n-Name`**: Name format assumptions (first/last)
- **`i18n-Payment`**: Payment method region assumptions
- **`i18n-Units`**: Hardcoded measurement units (miles, kg, fahrenheit)
- **`i18n-Encoding`**: ASCII-only assumptions, non-UTF8 handling
- **`i18n-FeatureFlags`**: Region-unaware feature flags
- **`i18n-BestPractice`**: Missing i18n utilities, lack of fallbacks
- **`God-Object`**: Files with 500+ lines, 20+ methods
- **`God-Function`**: Functions with 50+ lines, 5+ parameters
- **`Hardcoded-Configuration`**: Values that should be configurable
- **`Hardcoded-UI-Text`**: User-facing strings in code
- **`Global-State-Anti-Pattern`**: Global mutable state

## Severity Guidelines

**As per detection-rules.md Importance Classification:**

IMPORTANT: All i18n violations should use importance values of **8 or higher**.

- **critical** (9-10):
  - Breaks functionality in other regions
  - Security risk or payment failures
  - Hardcoded currency/country breaking international adoption
  - Missing geo context in experiment frameworks

- **high** (7-8):
  - Significantly degrades UX in other regions
  - Prevents market adoption
  - Compliance issues
  - Maintainability concerns causing technical debt

- **medium** (4-6):
  - Should NOT be used for i18n violations per detection-rules.md
  - Only for non-i18n issues

- **low** (1-3):
  - Should NOT be used for i18n violations per detection-rules.md

## Decision Rules (i18n-Specific)

### Analysis Steps for Each Comment

1. **Identify Original Violation**: What i18n rule was violated in the original code?
2. **Compare Changes**: What changed between the original code and current code?
3. **Check Violation Status**: Does the current code still violate the same i18n rule?
4. **Evaluate Solution Validity**: Is the solution valid, even if different from suggestion?

### Mark as ADDRESSED (true) if:

**Primary Criteria** (Violation Resolution):
✅ The i18n violation from detection-rules.md is **no longer present** in current code
✅ The code **does not violate** any other i18n rules from detection-rules.md
✅ The solution **follows** best-practices.md principles (even if using different approach than suggested)

**Specific Examples**:
✅ The code no longer exists (file deleted or code removed)
✅ Hardcoded values replaced with **any** valid parameterized/externalized approach
✅ Anti-patterns from `detection-rules.md` corrected with **any** proper implementation
✅ **Any** language-specific correct pattern from `language-patterns.md` applied (not just the suggested one)
✅ **Any** i18n library/utility used (GeoSDK, i18nify, DCS, or other valid alternatives)
✅ Timestamps stored in UTC and displayed localized (implementation may vary)
✅ Country dimension added to logs/metrics (approach may vary)
✅ Feature flags made country-aware (implementation may vary)
✅ Developer provided valid technical explanation aligned with best-practices.md
✅ Issue was false positive and explained clearly
✅ **Alternative valid solution** that resolves the violation (even if not the suggested fix)

**Key Point**: If the violation is resolved and no new violations introduced, mark as ADDRESSED regardless of whether the exact suggested solution was used.

### Mark as NOT ADDRESSED (false) if:

**Primary Criteria** (Violation Still Present):
❌ The **same i18n violation** from detection-rules.md is **still present** in current code
❌ Code **still violates** the same i18n rule, even with modifications

**Specific Examples**:
❌ Code unchanged and anti-pattern from `detection-rules.md` still present
❌ Hardcoded currency/country/timezone/phone patterns **still exist** (even if different values)
❌ Still violates best-practices.md principles (not parameterized, not externalized)
❌ Language-specific anti-pattern from `language-patterns.md` still present
❌ Missing country context in observability (logs/metrics) where it was flagged
❌ Feature flags still region-unaware
❌ No valid explanation from developer when code unchanged
❌ Fix is incomplete (partially addressed but core violation remains)
❌ Still fails "Fail-Safe by Default" principle (assumes instead of rejects)
❌ **New i18n violation introduced** while fixing the original one

### Examples of Valid Alternative Solutions

**Hardcoded Currency "USD"**:
- ✅ Suggested: `getCurrency(userLocale)`
- ✅ Also valid: `config.get('currency')`, `user.preferredCurrency`, `i18nify.currency()`, `currencyService.getCurrency()`
- ❌ Still invalid: `const currency = "EUR"` (still hardcoded, different value)

**Hardcoded Country Check `if (country == "IN")`**:
- ✅ Suggested: `geoSDK.GetConfig(country)`
- ✅ Also valid: `config.isFeatureEnabled(country)`, `countryService.getSettings(country)`, `regionConfig[country]`
- ❌ Still invalid: `if (country == "MY")` (still hardcoded check, different country)

**Hardcoded Date Format "MM/DD/YYYY"**:
- ✅ Suggested: `getDateFormat(userLocale)`
- ✅ Also valid: `date.toLocaleDateString(locale)`, `moment(date).format(localeFormat)`, `Intl.DateTimeFormat(locale)`
- ❌ Still invalid: `"DD/MM/YYYY"` (still hardcoded, different format)

## Example Analysis

### Example 0: Currency Symbol Hardcoding - Fixed with i18nify (Real Case)

**Input Comment:**
```json
{
  "comment_id": "2827200630",
  "body": "Hardcoded currency symbols and country code confusion prevents international payment processing. Use the existing goutils/currency package which provides proper currency metadata. [I18N, importance: 10]",
  "file_path": "internal/common/common_util.go",
  "line": 123
}
```

**Original Code (from comment):**
```go
func GetCurrencySymbol(countryCode string) string {
    switch countryCode {
    case "US":
        return "$"
    case "IN":
        return "Rs."
    case "GBP":
        return "£"
    default:
        return "Rs."
    }
}
```

**Current Code Found:**
```go
import i18nify_go "github.com/razorpay/i18nify/packages/i18nify-go"

func GetCurrencySymbol(countryCode string) string {
    country := i18nify_go.NewCountry(countryCode)
    currencyMtd := country.GetCountryCurrency()
    if len(currencyMtd) == 0 {
        return ""
    }
    return currencyMtd[0].Symbol
}
```

**Analysis Output:**
```json
{
  "comment_id": "2827200630",
  "addressed": true,
  "confidence": "high",
  "reasoning": "Hardcoded currency symbols and country/currency confusion completely resolved. Developer replaced switch statement with i18nify_go library which properly maps country → currency → symbol. No longer hardcodes 'Rs.', '$', '£'. Violation resolved per detection-rules.md [i18n-Currency]. Follows best-practices.md externalization principle using i18nify.",
  "severity": "critical",
  "category": "i18n-Currency"
}
```

---

### Example 1: Currency Violation - Exact Solution Implemented

**Input Comment:**
```json
{
  "comment_id": "123",
  "body": "[i18n-Currency, importance: 10] Hardcoded currency 'USD'. Should use getCurrency(userLocale)",
  "file_path": "src/services/payment.js",
  "line": 45
}
```

**Original Code (from comment):**
```javascript
const currency = "USD";  // Hardcoded violation
```

**Current Code Found:**
```javascript
const currency = getCurrency(userLocale);
const price = formatCurrency(amount, userLocale);
```

**Analysis Output:**
```json
{
  "comment_id": "123",
  "addressed": true,
  "confidence": "high",
  "reasoning": "Hardcoded currency 'USD' removed. Developer used suggested getCurrency(userLocale). Violation resolved per detection-rules.md [i18n-Currency]. Follows best-practices.md externalization principle.",
  "severity": "critical",
  "category": "i18n-Currency"
}
```

---

### Example 2: Currency Violation - Alternative Valid Solution

**Input Comment:**
```json
{
  "comment_id": "125",
  "body": "[i18n-Currency, importance: 10] Hardcoded currency 'USD'. Should use getCurrency(userLocale)",
  "file_path": "src/api/pricing.py",
  "line": 32
}
```

**Original Code (from comment):**
```python
currency = "USD"  # Hardcoded violation
```

**Current Code Found:**
```python
currency = config.get('merchant.currency') or user.preferred_currency
```

**Analysis Output:**
```json
{
  "comment_id": "125",
  "addressed": true,
  "confidence": "high",
  "reasoning": "Hardcoded currency 'USD' removed. Developer used alternative solution (config-based + user preference) instead of suggested getCurrency(). Violation resolved - no hardcoded currency. Solution valid per best-practices.md externalization principle.",
  "severity": "critical",
  "category": "i18n-Currency"
}
```

---

### Example 3: Region Violation - Different Approach, Still Valid

**Input Comment:**
```json
{
  "comment_id": "126",
  "body": "[i18n-Region, importance: 9] Hardcoded country check 'if (country == \"IN\")'. Should use geoSDK.GetConfig(country)",
  "file_path": "src/features/payment_methods.go",
  "line": 45
}
```

**Original Code (from comment):**
```go
if country == "IN" {
    EnableUPIPayment()
}
```

**Current Code Found:**
```go
allowedMethods := paymentConfig.GetMethodsByCountry(country)
if contains(allowedMethods, "UPI") {
    EnableUPIPayment()
}
```

**Analysis Output:**
```json
{
  "comment_id": "126",
  "addressed": true,
  "confidence": "high",
  "reasoning": "Hardcoded country check removed. Developer used paymentConfig.GetMethodsByCountry() instead of suggested geoSDK. Violation resolved - no hardcoded country comparison. Solution valid per best-practices.md parameterization principle.",
  "severity": "critical",
  "category": "i18n-Region"
}
```

---

### Example 4: Region Violation - Still Not Addressed (Different Hardcoded Value)

**Input Comment:**
```json
{
  "comment_id": "127",
  "body": "[i18n-Region, importance: 9] Hardcoded country check 'if (country_code == \"IN\")'. Should use geoSDK.GetConfig(country)",
  "file_path": "src/features/payment_methods.py",
  "line": 67
}
```

**Original Code (from comment):**
```python
if country_code == "IN":
    enable_upi_payment()
```

**Current Code Found:**
```python
if country_code == "MY":  # Changed to Malaysia, but still hardcoded
    enable_ewallet_payment()
DEFAULT_COUNTRY = "US"
```

**Analysis Output:**
```json
{
  "comment_id": "127",
  "addressed": false,
  "confidence": "high",
  "reasoning": "Hardcoded country check still present (changed from 'IN' to 'MY' but still violates same rule). Violation NOT resolved per detection-rules.md [i18n-Region]. Still fails best-practices.md parameterization principle. Should use dynamic country-based config.",
  "severity": "critical",
  "category": "i18n-Region"
}
```

---

### Example 5: DateTime Violation - Multiple Valid Implementations

**Input Comment:**
```json
{
  "comment_id": "128",
  "body": "[i18n-DateTime, importance: 8] Hardcoded date format 'MM/DD/YYYY'. Use getDateFormat(userLocale)",
  "file_path": "components/DatePicker.tsx",
  "line": 23
}
```

**Original Code (from comment):**
```typescript
const formatted = date.format("MM/DD/YYYY");  // Hardcoded US format
```

**Current Code Found:**
```typescript
const formatted = new Intl.DateTimeFormat(userLocale, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit'
}).format(date);
```

**Analysis Output:**
```json
{
  "comment_id": "128",
  "addressed": true,
  "confidence": "high",
  "reasoning": "Hardcoded format removed. Developer used Intl.DateTimeFormat instead of suggested getDateFormat(). Both are valid per language-patterns.md JavaScript patterns. Violation resolved - date formatting now locale-aware.",
  "severity": "high",
  "category": "i18n-DateTime"
}
```
