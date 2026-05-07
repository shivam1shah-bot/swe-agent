# Currency Patterns

## Library

**Always use i18nify**: `github.com/razorpay/i18nify`

- Go: `github.com/razorpay/i18nify-go`
- JS/React: `@razorpay/i18nify-js`

## Storage

Store amounts in **minor units** (smallest currency unit) as integers:

```go
type Payment struct {
    AmountMinorUnits int64  `json:"amount"` // paise, cents, sen
    Currency         string `json:"currency"` // ISO 4217: INR, MYR, SGD
}
```

## Go Examples

```go
import (
    "github.com/razorpay/i18nify-go/currency"
)

// Convert major to minor units
minorUnits := currency.ConvertToMinorUnit(100.50, "MYR") // 10050

// Convert minor to major units
majorUnits := currency.ConvertToMajorUnit(10050, "MYR") // 100.50

// Format for display
formatted := currency.Format(10050, "MYR", "en-MY") // "RM 100.50"

// Get currency symbol
symbol := currency.GetSymbol("MYR") // "RM"

// Validate currency code
isValid := currency.IsValid("MYR") // true

// Get decimal places for currency
decimals := currency.GetDecimals("MYR") // 2
decimals := currency.GetDecimals("JPY") // 0
```

## JavaScript Examples

```javascript
import { 
    convertToMinorUnit, 
    convertToMajorUnit, 
    formatNumber,
    getCurrencySymbol,
    getCurrencyList 
} from '@razorpay/i18nify-js';

// Convert major to minor units
const minorUnits = convertToMinorUnit(100.50, { currency: 'MYR' }); // 10050

// Convert minor to major units  
const majorUnits = convertToMajorUnit(10050, { currency: 'MYR' }); // 100.50

// Format for display
const formatted = formatNumber(10050, {
    currency: 'MYR',
    locale: 'en-MY',
    intlOptions: {
        style: 'currency',
        currency: 'MYR'
    }
}); // "RM 100.50"

// Get currency symbol
const symbol = getCurrencySymbol('MYR'); // "RM"
```

## Anti-Patterns

```go
// ❌ NEVER - hardcoded currency
const defaultCurrency = "INR"
amount := fmt.Sprintf("₹%.2f", total)

// ❌ NEVER - assume 2 decimal places
minorUnits := int64(amount * 100)

// ❌ NEVER - hardcoded symbols
symbol := "₹"
if country == "MY" {
    symbol = "RM"
}

// ✅ ALWAYS - use i18nify
currency := merchant.GetCurrency() // from Account Service
minorUnits := currency.ConvertToMinorUnit(amount, currency)
formatted := currency.Format(minorUnits, currency, locale)
```

## Database Schema

```sql
-- Store minor units and currency code
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    amount_minor_units BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL, -- ISO 4217
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Multi-currency balances
CREATE TABLE account_balances (
    account_id BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    balance_minor_units BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, currency)
);
```

## Supported Currencies

i18nify supports all ISO 4217 currencies. Common ones at Razorpay:

| Code | Symbol | Decimals | Region |
|------|--------|----------|--------|
| INR | ₹ | 2 | India |
| MYR | RM | 2 | Malaysia |
| SGD | S$ | 2 | Singapore |
| USD | $ | 2 | United States |
| JPY | ¥ | 0 | Japan |
| BHD | BD | 3 | Bahrain |
