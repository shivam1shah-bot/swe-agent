# Phone Number Patterns

## Library

**Always use i18nify**: `github.com/razorpay/i18nify`

## Storage Format

Store phone numbers in **E.164 format** as a single field:

```
+[country_code][number]
```

Examples:
- India: `+919876543210`
- Malaysia: `+60123456789`
- Singapore: `+6591234567`
- US: `+14155551234`

## Go Examples

```go
import (
    "github.com/razorpay/i18nify-go/phone"
)

// Parse and validate phone number
parsed, err := phone.Parse("+60123456789")
if err != nil {
    return fmt.Errorf("invalid phone: %w", err)
}

// Validate for specific country
isValid := phone.IsValidForCountry("+60123456789", "MY") // true

// Validate E.164 format
isE164 := phone.IsValidE164("+60123456789") // true

// Format for display
display := phone.FormatNational("+60123456789", "MY") // "012-345 6789"
display := phone.FormatInternational("+60123456789") // "+60 12-345 6789"

// Get country from phone number
country := phone.GetCountryCode("+60123456789") // "MY"

// Get dial code for country
dialCode := phone.GetDialCode("MY") // "+60"
```

## JavaScript Examples

```javascript
import { 
    parsePhoneNumber,
    isValidPhoneNumber,
    formatPhoneNumber,
    getDialCode 
} from '@razorpay/i18nify-js';

// Parse phone number
const parsed = parsePhoneNumber('+60123456789');

// Validate phone number
const isValid = isValidPhoneNumber('+60123456789', 'MY'); // true

// Format for display
const formatted = formatPhoneNumber('+60123456789', 'MY'); // "012-345 6789"

// Get dial code
const dialCode = getDialCode('MY'); // "+60"
```

## Country Code Source

Country code for phone validation comes from **customer country** or **merchant country**:

```go
// Get country from customer (preferred for phone validation)
country := customer.GetCountryCode()

// Or from merchant if customer country not available
if country == "" {
    country = merchant.GetCountryCode()
}

// Validate phone for that country
if !phone.IsValidForCountry(req.Phone, country) {
    return fmt.Errorf("invalid phone for %s", country)
}
```

## Anti-Patterns

```go
// ❌ NEVER - hardcoded dial codes
if strings.HasPrefix(phone, "+91") {
    // India logic
}

// ❌ NEVER - hardcoded regex
phoneRegex := regexp.MustCompile(`^\+91\d{10}$`)

// ❌ NEVER - assume country
parsed, _ := libphonenumber.Parse(phone, "IN")

// ❌ NEVER - store separately
type Contact struct {
    CountryCode string // +60
    PhoneNumber string // 123456789
}

// ✅ ALWAYS - use i18nify with dynamic country
country := customer.GetCountryCode()
if !phone.IsValidForCountry(req.Phone, country) {
    return fmt.Errorf("invalid phone for %s", country)
}

// ✅ ALWAYS - store E.164
type Contact struct {
    Phone string `json:"phone"` // +60123456789
}
```

## Database Schema

```sql
-- Single field, E.164 format
CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY,
    phone VARCHAR(20) NOT NULL, -- E.164: +60123456789
    country_code VARCHAR(2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for phone lookups
CREATE INDEX idx_customers_phone ON customers(phone);
```

## Validation Flow

```go
func ValidatePhone(phone string, country string) error {
    // 1. Check country is provided
    if country == "" {
        return errors.New("country_code required for phone validation")
    }
    
    // 2. Validate E.164 format
    if !phone.IsValidE164(phone) {
        return errors.New("phone must be in E.164 format")
    }
    
    // 3. Validate for specific country
    if !phone.IsValidForCountry(phone, country) {
        return fmt.Errorf("invalid phone number for %s", country)
    }
    
    return nil
}
```
