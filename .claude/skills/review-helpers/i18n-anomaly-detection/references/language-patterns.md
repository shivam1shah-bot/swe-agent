# Language-Specific Detection Patterns

This document contains detection patterns specific to different programming languages and frameworks.

## JavaScript / TypeScript

### Common i18n Violations

**Window Location & Region Detection:**
```javascript
// Bad
if (window.location.hostname.includes('us')) {
    currency = 'USD';
}

// Good
const currency = getUserCurrency();
```

**Date Constructor Without Locale:**
```javascript
// Bad
const date = new Date();
const formatted = date.toLocaleDateString(); // uses system locale

// Good
const formatted = date.toLocaleDateString(userLocale, options);
```

**Number Formatting:**
```javascript
// Bad
const price = Number(amount).toFixed(2); // no locale

// Good
const price = new Intl.NumberFormat(userLocale, {
    style: 'currency',
    currency: userCurrency
}).format(amount);
```

**String Comparison for Codes:**
```javascript
// Bad
if (countryCode === 'US' || countryCode === 'CA') {
    // North America logic
}

// Good
if (NORTH_AMERICA_COUNTRIES.includes(countryCode)) {
    // Region-aware logic
}
```

### TypeScript-Specific Patterns

**Type Definitions:**
```typescript
// Bad
type Currency = 'USD' | 'EUR' | 'INR'; // limited set

// Good
type Currency = string; // or import from i18n config
```

---

## Python

### Common i18n Violations

**Datetime Without Timezone:**
```python
# Bad
from datetime import datetime
now = datetime.now() # naive datetime

# Good
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
# or
import pytz
now = datetime.now(pytz.timezone(user_timezone))
```

**Locale Module Misuse:**
```python
# Bad
import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8') # hardcoded

# Good
import locale
user_locale = get_user_locale()
locale.setlocale(locale.LC_ALL, user_locale)
```

**Hardcoded String Formatting:**
```python
# Bad
price = f"${amount:.2f}"
date_str = f"{month}/{day}/{year}"

# Good
price = format_currency(amount, user_currency, user_locale)
date_str = format_date(date_obj, user_locale)
```

**Currency/Country Constants:**
```python
# Bad
DEFAULT_CURRENCY = "USD"
SUPPORTED_COUNTRIES = ["US", "UK", "CA"]

# Good
DEFAULT_CURRENCY = config.get("default_currency")
SUPPORTED_COUNTRIES = config.get("supported_countries")
```

---

## Java

### Common i18n Violations

**SimpleDateFormat Without Locale:**
```java
// Bad
SimpleDateFormat sdf = new SimpleDateFormat("MM/dd/yyyy");

// Good
DateFormat df = DateFormat.getDateInstance(
    DateFormat.SHORT,
    userLocale
);
```

**Currency.getInstance() Hardcoded:**
```java
// Bad
Currency usd = Currency.getInstance("USD");

// Good
Currency currency = Currency.getInstance(userLocale);
```

**Locale.getDefault() Assumptions:**
```java
// Bad
Locale locale = Locale.getDefault(); // system locale, not user's

// Good
Locale locale = getUserLocale();
```

**NumberFormat Without Locale:**
```java
// Bad
NumberFormat nf = NumberFormat.getInstance();

// Good
NumberFormat nf = NumberFormat.getCurrencyInstance(userLocale);
```

### Resource Bundle Issues

```java
// Bad
String message = "Welcome to our application";

// Good
ResourceBundle bundle = ResourceBundle.getBundle(
    "Messages",
    userLocale
);
String message = bundle.getString("welcome.message");
```

---

## Go

### Common i18n Violations

**time.Parse() With Fixed Formats:**
```go
// Bad
t, err := time.Parse("2006-01-02", dateString)
const DateFormat = "01/02/2006" // US format

// Good
format := getDateFormat(userLocale)
t, err := time.Parse(format, dateString)
```

**strconv.Format* Without Locale:**
```go
// Bad
price := strconv.FormatFloat(amount, 'f', 2, 64)

// Good
import "golang.org/x/text/message"
p := message.NewPrinter(language.Make(userLocale))
price := p.Sprintf("%.2f", amount)
```

**Hardcoded Country/Currency Constants:**
```go
// Bad
const (
    DefaultCountry  = "US"
    DefaultCurrency = "USD"
)

// Good
var (
    DefaultCountry  = config.GetString("default.country")
    DefaultCurrency = config.GetString("default.currency")
)
```

**Geographic Routing Logic:**
```go
// Bad
if user.Country == "IN" {
    return processIndiaPayment(payment)
}

// Good
processor := getPaymentProcessor(user.Country, payment.Method)
return processor.Process(payment)
```

---

## React / Vue / Angular

### React-Specific Patterns

**Hardcoded Text in Components:**
```jsx
// Bad
function Welcome() {
    return <h1>Welcome to our app</h1>;
}

// Good
import { useTranslation } from 'react-i18next';

function Welcome() {
    const { t } = useTranslation();
    return <h1>{t('welcome.title')}</h1>;
}
```

**Date/Number Formatting:**
```jsx
// Bad
function Price({ amount }) {
    return <span>${amount.toFixed(2)}</span>;
}

// Good
import { useIntl } from 'react-intl';

function Price({ amount }) {
    const intl = useIntl();
    return <span>
        {intl.formatNumber(amount, {
            style: 'currency',
            currency: intl.locale.currency
        })}
    </span>;
}
```

**Conditional Rendering Based on Hardcoded Regions:**
```jsx
// Bad
function PaymentMethods({ country }) {
    return (
        <>
            {country === 'IN' && <UPIOption />}
            {country === 'US' && <CreditCardOption />}
        </>
    );
}

// Good
function PaymentMethods({ country }) {
    const methods = getAvailablePaymentMethods(country);
    return methods.map(method => (
        <PaymentOption key={method.id} method={method} />
    ));
}
```

**Component Props Without Locale Context:**
```jsx
// Bad
<DatePicker format="MM/DD/YYYY" />

// Good
import { useLocale } from './i18n';

function MyComponent() {
    const { dateFormat } = useLocale();
    return <DatePicker format={dateFormat} />;
}
```

### Vue-Specific Patterns

**Template Hardcoded Text:**
```vue
<!-- Bad -->
<template>
    <button>Submit</button>
</template>

<!-- Good -->
<template>
    <button>{{ $t('buttons.submit') }}</button>
</template>
```

**Filters for Formatting:**
```vue
<!-- Bad -->
<template>
    <span>{{ price.toFixed(2) }}</span>
</template>

<!-- Good -->
<template>
    <span>{{ price | currency }}</span>
</template>

<script>
export default {
    filters: {
        currency(value) {
            return this.$n(value, 'currency');
        }
    }
}
</script>
```

### Angular-Specific Patterns

**Hardcoded Strings in Templates:**
```html
<!-- Bad -->
<button>Click Here</button>

<!-- Good -->
<button>{{ 'buttons.click' | translate }}</button>
```

**Date Pipe Without Locale:**
```html
<!-- Bad -->
<span>{{ date | date:'MM/dd/yyyy' }}</span>

<!-- Good -->
<span>{{ date | date:'short':undefined:locale }}</span>
```

---

## SQL / Database Queries

### Common Issues

**Hardcoded Timezone in Queries:**
```sql
-- Bad
SELECT * FROM orders
WHERE created_at > '2024-01-01 00:00:00 PST'

-- Good
SELECT * FROM orders
WHERE created_at > @start_timestamp
-- Pass timestamp in user's timezone from application
```

**Currency in Schema:**
```sql
-- Bad
CREATE TABLE products (
    price DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD'
)

-- Better (but still need app-level handling)
CREATE TABLE products (
    price DECIMAL(10,2),
    currency VARCHAR(3) NOT NULL
)
```

---

## Configuration Files

### JSON/YAML Configuration

**Hardcoded Regional Settings:**
```yaml
# Bad
default:
  country: US
  currency: USD
  timezone: America/New_York
  language: en

# Good
default:
  country: ${DEFAULT_COUNTRY}
  currency: ${DEFAULT_CURRENCY}
  timezone: ${DEFAULT_TIMEZONE}
  language: ${DEFAULT_LANGUAGE}
```

### Feature Flags

**Region-Unaware Flags:**
```json
// Bad
{
  "new_feature": true
}

// Good
{
  "new_feature": {
    "enabled": true,
    "regions": ["US", "CA", "UK"],
    "rollout_percentage": 50
  }
}
```

---

## API Responses

### REST API Patterns

**Hardcoded Values in Responses:**
```javascript
// Bad
app.get('/config', (req, res) => {
    res.json({
        currency: 'USD',
        dateFormat: 'MM/DD/YYYY'
    });
});

// Good
app.get('/config', (req, res) => {
    const userLocale = getUserLocale(req);
    res.json({
        currency: getCurrency(userLocale),
        dateFormat: getDateFormat(userLocale)
    });
});
```

---

## Testing Code

### Test Fixtures with Hardcoded Values

```javascript
// Bad
const testUser = {
    country: 'US',
    currency: 'USD',
    timezone: 'America/New_York'
};

// Good
const createTestUser = (overrides = {}) => ({
    country: overrides.country || config.get('test.default.country'),
    currency: overrides.currency || config.get('test.default.currency'),
    timezone: overrides.timezone || config.get('test.default.timezone'),
    ...overrides
});
```

---

## Search Strategy by Language

| Language | Key Files | Primary Patterns |
|----------|-----------|------------------|
| **JavaScript/TS** | `*.js`, `*.ts`, `*.jsx`, `*.tsx` | `new Date()`, `toFixed()`, hardcoded strings in JSX |
| **Python** | `*.py` | `datetime.now()`, `locale.*`, f-strings with hardcoded formats |
| **Java** | `*.java` | `SimpleDateFormat`, `Currency.getInstance()`, `Locale.getDefault()` |
| **Go** | `*.go` | `time.Parse()`, `strconv.*`, hardcoded constants |
| **React** | `*.jsx`, `*.tsx` | Hardcoded text in components, missing `useTranslation()` |
| **Vue** | `*.vue` | Template strings, missing `$t()`, `$n()` |
| **Angular** | `*.html`, `*.ts` | Missing `translate` pipe, hardcoded date formats |
| **SQL** | `*.sql` | Timezone in timestamps, default currency values |
| **Config** | `*.json`, `*.yaml`, `*.yml` | Hardcoded regional defaults |
