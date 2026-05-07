# Detection Rules and Patterns

This document contains comprehensive detection rules for all violation categories.

## i18n Violation Categories

### [i18n-Currency]

**What to Look For:**
- Hardcoded currency codes (USD, EUR, INR, etc.)
- Fixed currency symbols ($, €, ₹, etc.)
- Currency formatting without locale consideration
- Hardcoded denomination factors or conversion rates
- Missing currency conversion logic

**Examples:**
```javascript
// Bad
const currency = "USD";
const price = "$" + amount;
const converted = amount * 0.012; // hardcoded conversion rate

// Good
const currency = getCurrency(userLocale);
const price = formatCurrency(amount, userLocale);
const converted = convertCurrency(amount, fromCurrency, toCurrency);
```

**Search Patterns:**
- Regex: `/USD|EUR|INR|GBP|JPY/`
- Regex: `/\$|\€|\₹/`
- Functions: `formatCurrency()`, `convertTo`
- String literals: `"USD"`, `"EUR"`, `"INR"`

---

### [i18n-Region]

**What to Look For:**
- Hardcoded country codes (US, IN, UK, etc.)
- Fixed region names (India, America, etc.)
- Country-specific business logic
- Geolocation assumptions

**Examples:**
```python
# Bad
if country_code == "IN":
    enable_upi_payment()
DEFAULT_COUNTRY = "US"

# Good
if is_payment_method_available("upi", country_code):
    enable_upi_payment()
country = get_user_country()
```

**Search Patterns:**
- Regex: `/country.*==/`, `/region.*=/`
- String literals: `"IN"`, `"US"`, `"UK"`, `"DE"`
- Conditionals checking hardcoded country codes

---

### [i18n-Phone]

**What to Look For:**
- Hardcoded country codes for phone parsing (+1, +91, etc.)
- Fixed phone number formats
- Country-specific phone validation
- Dial code assumptions

**Examples:**
```javascript
// Bad
const phoneRegex = /^\+1\d{10}$/;
libphonenumber.parse(number, "US");

// Good
const phoneRegex = getPhonePattern(countryCode);
libphonenumber.parse(number, countryCode);
```

**Search Patterns:**
- Regex: `/\+\d{1,3}/`
- Function calls: `parsePhoneNumber.*"[A-Z]{2}"`
- Variables: `phoneFormat`, `dialCode`

---

### [i18n-DateTime]

**What to Look For:**
- Hardcoded date formats (MM/DD/YYYY, DD/MM/YYYY)
- Fixed time parsing patterns
- Locale-unaware date operations
- Non-configurable date display

**Examples:**
```go
// Bad
time.Parse("2006-01-02", dateString)
const format = "MM/DD/YYYY"

// Good
time.Parse(getDateFormat(locale), dateString)
const format = getDateFormat(userLocale)
```

**Search Patterns:**
- Regex: `/\d{2}\/\d{2}\/\d{4}/`
- Function calls: `Parse.*"2006-01-02"`
- Variables: `dateFormat`, `DATE_FORMAT`

---

### [i18n-Timezone]

**What to Look For:**
- Hardcoded timezone names (UTC, EST, IST)
- Fixed timezone conversions
- Default timezone assumptions
- Business hours assumptions

**Examples:**
```python
# Bad
tz = pytz.timezone("America/New_York")
DEFAULT_TZ = "UTC"

# Good
tz = pytz.timezone(user.timezone)
default_tz = get_default_timezone(user_region)
```

**Search Patterns:**
- Function calls: `LoadLocation.*"America/`
- String literals: `"UTC"`, `"GMT"`, `"EST"`, `"PST"`
- Variables: `timezone.*=`

---

### [i18n-Address]

**What to Look For:**
- Hardcoded address formats
- Fixed postal code patterns
- Country-specific address validation
- State/province assumptions

**Examples:**
```javascript
// Bad
const zipRegex = /^\d{5}(-\d{4})?$/; // US ZIP only
const address = `${street}, ${city}, ${state} ${zip}`;

// Good
const postalRegex = getPostalCodePattern(countryCode);
const address = formatAddress(addressData, countryCode);
```

**Search Patterns:**
- Regex: `/\d{5}(-\d{4})?/`
- Variables: `zipcode`, `postalcode`, `addressFormat`

---

### [i18n-Language]

**What to Look For:**
- Hardcoded text strings in user interfaces
- English-only error messages
- Fixed language assumptions
- Non-externalized user-facing text

**Examples:**
```jsx
// Bad
<button>Submit</button>
alert("Processing...");
throw new Error("Invalid input");

// Good
<button>{t('common.submit')}</button>
alert(t('messages.processing'));
throw new Error(t('errors.invalid_input'));
```

**Search Patterns:**
- String literals in UI components: `"Please wait"`, `"Error:"`, `"Success"`
- Alert/notification messages
- Button text, labels, titles

---

### [i18n-Branding]

**What to Look For:**
- Hardcoded company/product names in code
- Fixed branding elements
- Non-configurable brand text
- Logo/image paths hardcoded

**Examples:**
```python
# Bad
company_name = "Acme Corp"
logo_path = "/static/images/acme-logo.png"

# Good
company_name = get_brand_config("company_name")
logo_path = get_brand_asset("logo")
```

**Search Patterns:**
- Variables: `companyName`, `brandName`
- Paths: `logo.*"static/`
- Variables: `brandColor`, `COMPANY_NAME`

---

### [i18n-Name]

**What to Look For:**
- Assumptions about name formats (first/last)
- Fixed name validation patterns
- Western name structure assumptions
- Middle name requirements

**Examples:**
```javascript
// Bad
const fullName = firstName + " " + lastName;
const parts = name.split(" "); // assumes space-separated

// Good
const fullName = formatName(nameObject, locale);
const nameComponents = parseName(fullName, locale);
```

**Search Patterns:**
- Operations: `firstName.*lastName`
- String operations: `fullName.*split`
- Variables: `nameValidation`

---

### [i18n-Payment]

**What to Look For:**
- Payment method assumptions by region
- Hardcoded payment provider logic
- Region-specific payment flows
- Currency-method coupling

**Examples:**
```python
# Bad
if country == "IN":
    payment_methods = ["UPI", "NetBanking"]
elif country == "US":
    payment_methods = ["CreditCard", "PayPal"]

# Good
payment_methods = get_available_payment_methods(country, currency)
```

**Search Patterns:**
- Conditionals: `paymentMethod.*country`
- Region checks: `if.*"IN".*upi`, `paypal.*us`

---

### [i18n-Units]

**What to Look For:**
- Fixed measurement units (miles, kg, fahrenheit)
- Hardcoded unit conversions
- Non-configurable unit display
- Temperature/distance assumptions

**Examples:**
```javascript
// Bad
const distance = miles + " miles";
const temp = fahrenheit + "°F";

// Good
const distance = formatDistance(value, userLocale);
const temp = formatTemperature(value, userLocale);
```

**Search Patterns:**
- String literals: `"miles"`, `"km"`, `"fahrenheit"`, `"celsius"`
- Functions: `convertTo.*Miles`

---

### [i18n-Encoding]

**What to Look For:**
- ASCII-only assumptions
- Fixed character encoding
- Non-UTF8 handling
- Byte length assumptions for text

**Examples:**
```go
// Bad
if len(str) > 100 { // byte length, not character count
    return errors.New("too long")
}

// Good
if utf8.RuneCountInString(str) > 100 {
    return errors.New("too long")
}
```

**Search Patterns:**
- Character sets: `ASCII`, `latin1`
- Length operations: `len\(.*\).*string`
- Encoding: `encoding.*ascii`

---

### [i18n-FeatureFlags]

**What to Look For:**
- Region-unaware feature flags
- Hardcoded feature availability
- Country-specific feature logic
- Geographic feature gating

**Examples:**
```javascript
// Bad
const feature_enabled = country === "US";
if (region === "NA") enableFeature();

// Good
const feature_enabled = isFeatureEnabled("feature_name", {country, user});
```

**Search Patterns:**
- Conditionals: `feature.*enabled.*country`
- String checks: `flag.*"US"`
- Variables: `experiment.*region`

---

### [i18n-BestPractice]

**What to Look For:**
- Missing i18n utility usage
- Lack of try-catch around i18n calls
- Missing fallback logic for i18n failures
- No India-specific fallbacks where required

**Examples:**
```javascript
// Bad
const price = amount.toString(); // no formatting

// Good
try {
    const price = formatNumber(amount, locale);
} catch (e) {
    const price = amount.toString(); // fallback
}
```

**Search Patterns:**
- Missing functions: `formatNumber()`, `getCurrencySymbol()`, `parsePhoneNumber()`

---

## Anti-Pattern Categories

### [God Object]

**What to Look For:**
- Files with 500+ lines
- Classes/structs with 20+ methods
- Too many imports (15+ external packages)
- Multiple responsibilities in single entity

**Detection:**
- Count file lines
- Count class methods
- Count import statements
- Check for Single Responsibility Principle violations

**Example:**
```java
// Bad - God Object
public class OrderService {
    // 50+ methods handling validation, processing,
    // notification, billing, shipping, etc.
}

// Good - Single Responsibility
public class OrderValidator { }
public class OrderProcessor { }
public class OrderNotifier { }
```

---

### [God Function]

**What to Look For:**
- Functions with 50+ lines
- Functions with 5+ parameters
- Multiple responsibilities in single function
- Deep nesting (4+ levels)

**Detection:**
- Count function lines
- Count parameters
- Measure nesting depth
- Check for multiple distinct operations

**Example:**
```python
# Bad - God Function
def process_order(user_id, items, payment, shipping,
                  discount, tax, notes, preferences):
    # 100+ lines doing everything
    pass

# Good - Decomposed
def validate_order(user_id, items):
    pass

def calculate_total(items, discount, tax):
    pass

def process_payment(payment):
    pass
```

---

### [Hardcoded Configuration]

**What to Look For:**
- Values that should be configurable
- Magic numbers without constants
- Environment-specific hardcoded values
- Non-externalizable settings

**Examples:**
```go
// Bad
const apiUrl = "https://api.prod.example.com"
if retries > 3 { // magic number
    return
}

// Good
const apiUrl = config.Get("API_URL")
const maxRetries = config.GetInt("MAX_RETRIES")
if retries > maxRetries {
    return
}
```

**Search Patterns:**
- String literals: `const.*=.*"prod"`
- Hardcoded URLs, ports, timeouts
- Magic numbers in conditionals

---

### [Hardcoded UI Text]

**What to Look For:**
- User-facing strings in code
- Error messages not externalized
- Button text, labels, titles in templates
- Alert/notification text

**Examples:**
```jsx
// Bad
<button>Click Here</button>
<h1>Welcome to Our App</h1>
const error = "Something went wrong";

// Good
<button>{t('buttons.click_here')}</button>
<h1>{t('welcome.title')}</h1>
const error = t('errors.generic');
```

**Search Patterns:**
- Template literals: `alert.*"text"`, `title.*"string"`
- Placeholders: `placeholder.*"text"`

---

### [Global State Anti-Pattern]

**What to Look For:**
- Global variables for application state
- Singletons storing mutable state
- Static variables for configuration
- Shared mutable state without synchronization

**Examples:**
```javascript
// Bad
let currentUser = null; // global mutable state
class AppState {
    static config = {}; // singleton mutable state
}

// Good
class UserService {
    constructor(userRepository) {
        this.userRepository = userRepository;
    }
    getCurrentUser() {
        return this.userRepository.findCurrent();
    }
}
```

**Search Patterns:**
- Declarations: `var.*global`, `let.*=.*null` (at file scope)
- Patterns: `singleton.*state`, `static.*config`

---

## Analysis Instructions

1. **Prioritize substantial issues** that impact functionality, security, internationalization, or experiment validity
2. **Avoid minor style issues** like indentation or documentation
3. **Focus on patterns** that prevent international adoption or skew experiment results
4. **Identify security vulnerabilities** and performance bottlenecks
5. **Consolidate similar violations** in the same file under one comment
6. **Provide actionable recommendations** with specific alternatives
7. **Consider maintainability** and scalability implications
8. **Pay special attention** to experiment frameworks and their regional awareness
9. **Look for data collection patterns** that don't include geographic context
10. **Identify feature flags** and rollout strategies that ignore regional factors

## Importance Classification

Assign numeric importance scores (1-10) based on impact:

| Importance | Criteria |
|------------|----------|
| **10** | Breaks functionality in other regions, security risk, payment failures |
| **9** | Significantly degrades UX, prevents market adoption, compliance issues |
| **8** | Degraded experience, maintainability concerns, technical debt |
| **7 or below** | Should NOT be used for i18n violations |

**IMPORTANT**: All i18n violations should use importance values of 8 or higher.
