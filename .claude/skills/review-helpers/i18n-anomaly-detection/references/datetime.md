# DateTime & Timezone Patterns

## Library

**Always use i18nify**: `github.com/razorpay/i18nify`

## Core Principle

**Store UTC, Display Localized**

```
Storage: Always UTC
Display: User's timezone (from merchant/customer country)
```

## Storage

Always store timestamps in **UTC**:

```go
type Payment struct {
    CreatedAt time.Time `json:"created_at"` // Always UTC
    UpdatedAt time.Time `json:"updated_at"` // Always UTC
}

// When creating
payment.CreatedAt = time.Now().UTC()
```

## Timezone Source

| Context | Timezone Source |
|---------|-----------------|
| Merchant operations | Merchant country from Account Service |
| Customer-facing | Customer location |
| Multi-timezone countries | Handle appropriately (US has multiple, India has one) |

## Go Examples

```go
import (
    "github.com/razorpay/i18nify-go/datetime"
    "github.com/razorpay/i18nify-go/timezone"
)

// Get timezone for country
tz := timezone.GetTimezone("MY") // "Asia/Kuala_Lumpur"
tz := timezone.GetTimezone("IN") // "Asia/Kolkata"

// Format datetime for display
formatted := datetime.Format(payment.CreatedAt, "MY", "en-MY")
// Output: "15/01/2025 14:30"

// Format with specific pattern
formatted := datetime.FormatWithPattern(payment.CreatedAt, "MY", "dd MMM yyyy HH:mm")
// Output: "15 Jan 2025 14:30"

// Convert UTC to local timezone
localTime := datetime.ToTimezone(payment.CreatedAt, "Asia/Kuala_Lumpur")

// Parse user input in their timezone
parsed, err := datetime.ParseInTimezone("15/01/2025 14:30", "MY", "dd/MM/yyyy HH:mm")
// Returns UTC time

// Get locale for country
locale := datetime.GetLocale("MY") // "en-MY"
```

## JavaScript Examples

```javascript
import { formatDateTime, getTimezone } from '@razorpay/i18nify-js';

// Format datetime for display
const formatted = formatDateTime(payment.created_at, {
    locale: 'en-MY',
    intlOptions: {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Asia/Kuala_Lumpur'
    }
});

// Get timezone for country
const tz = getTimezone('MY'); // "Asia/Kuala_Lumpur"
```

## Anti-Patterns

```go
// ❌ NEVER - hardcoded timezone
loc, _ := time.LoadLocation("Asia/Kolkata")
istTime := time.Now().In(loc)

// ❌ NEVER - use time.Local
localTime := time.Now().In(time.Local)

// ❌ NEVER - hardcoded date format
formatted := t.Format("01/02/2006") // US format

// ❌ NEVER - assume IST
report.Date = time.Now().Format("2006-01-02 15:04:05 IST")

// ✅ ALWAYS - store UTC
createdAt := time.Now().UTC()

// ✅ ALWAYS - get timezone from country
tz := timezone.GetTimezone(merchant.GetCountryCode())
displayTime := datetime.Format(createdAt, merchant.GetCountryCode(), locale)
```

## Database Schema

```sql
-- Always use TIMESTAMP WITH TIME ZONE
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Never store as VARCHAR or without timezone
-- ❌ created_at VARCHAR(50)
-- ❌ created_at TIMESTAMP (without time zone)
```

## Backend/Frontend Consistency

Ensure both backend and frontend render the same localized time:

```go
// Backend API response
type PaymentResponse struct {
    CreatedAt    time.Time `json:"created_at"`     // UTC for storage/API
    DisplayTime  string    `json:"display_time"`   // Localized for UI
    Timezone     string    `json:"timezone"`       // For frontend reference
}

func ToResponse(p *Payment, merchant *Merchant) PaymentResponse {
    tz := timezone.GetTimezone(merchant.GetCountryCode())
    locale := datetime.GetLocale(merchant.GetCountryCode())
    
    return PaymentResponse{
        CreatedAt:   p.CreatedAt,
        DisplayTime: datetime.Format(p.CreatedAt, merchant.GetCountryCode(), locale),
        Timezone:    tz,
    }
}
```

```javascript
// Frontend - use timezone from response or merchant context
function displayPaymentTime(payment, merchant) {
    return formatDateTime(payment.created_at, {
        locale: merchant.locale,
        intlOptions: {
            dateStyle: 'medium',
            timeStyle: 'short',
            timeZone: merchant.timezone
        }
    });
}
```

## Multi-Timezone Countries

Some countries have multiple timezones (US, Australia, Russia). Handle appropriately:

```go
// For US, timezone might need to be more specific
// Option 1: Store user's specific timezone preference
// Option 2: Use a default for the country

func GetTimezoneForMerchant(merchant *Merchant) string {
    // If merchant has specific timezone preference, use it
    if merchant.TimezonePreference != "" {
        return merchant.TimezonePreference
    }
    
    // Otherwise use country default
    return timezone.GetDefaultTimezone(merchant.GetCountryCode())
}
```

## Report Generation

When generating reports, always clarify timezone:

```go
func GenerateReport(ctx context.Context, merchantID string, date string) (*Report, error) {
    merchant, _ := accountService.GetMerchant(ctx, merchantID)
    tz := timezone.GetTimezone(merchant.GetCountryCode())
    
    loc, _ := time.LoadLocation(tz)
    
    // Parse date in merchant's timezone
    startOfDay := time.Date(2025, 1, 15, 0, 0, 0, 0, loc)
    endOfDay := time.Date(2025, 1, 15, 23, 59, 59, 0, loc)
    
    // Convert to UTC for database query
    startUTC := startOfDay.UTC()
    endUTC := endOfDay.UTC()
    
    payments := db.GetPayments(merchantID, startUTC, endUTC)
    
    return &Report{
        Date:     date,
        Timezone: tz,
        Payments: payments,
    }, nil
}
```
