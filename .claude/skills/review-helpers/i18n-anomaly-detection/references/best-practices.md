# i18n Best Practices

## Guiding Principles

From Razorpay's "Think Global, Build Once" guide.

### Quick Reference

| Layer | Principle |
|-------|-----------|
| Infrastructure | Standardized, isolated, route globally |
| Application | Parameterize, externalize, localize, fail-safe |
| Observability | Country dimension everywhere |
| Testing | Multi-national test data |

---

## Application Engineering Principles

### 1. Parameterize Country Attribute

All behavior based on merchant's country from Account Service, not hardcoded.

```go
// ❌ Anti-pattern
if payment.MerchantCountry == "IN" {
    if payment.Amount < 100 { return errors.New("amount too low") }
} else if payment.MerchantCountry == "MY" {
    if payment.Amount < 1 { return errors.New("amount too low") }
}

// ✅ Correct
minAmount := geoSDK.GetMinimumAmount(payment.MerchantCountry, payment.Currency)
if payment.Amount < minAmount {
    return errors.New("amount too low")
}
```

### 2. Externalize & Centralize

Region-specific data lives outside codebase (GeoSDK, i18nify, DCS).

```go
// ❌ Anti-pattern: scattered constants
var TaxRates = map[string]float64{"IN": 18.0, "MY": 6.0}
var MinAmounts = map[string]int64{"INR": 100, "MYR": 100}

// ✅ Correct: centralized sources
taxRate := geoSDK.GetTaxRate(merchant.CountryCode)
minAmount := geoSDK.GetMinimumAmount(country, currency)
```

### 3. Localize at Presentation

Store canonical (UTC, minor units), display localized.

```go
// Storage
payment := Payment{
    AmountMinorUnits: 10000,
    Currency:         "MYR",
    CreatedAt:        time.Now().UTC(),
}

// Display
displayAmount := i18nify.FormatCurrency(payment.AmountMinorUnits, payment.Currency, locale)
displayTime := i18nify.FormatDateTime(payment.CreatedAt, merchant.Timezone)
```

### 4. Rollout Features Responsibly

Features disabled by default, enabled per country via DCS.

```go
// ❌ Anti-pattern: global feature
func ApplyOffer(payment *Payment, offerCode string) error {
    offer := fetchOffer(offerCode)
    if offer.IsValid() {
        payment.Discount = offer.CalculateDiscount(payment.Amount)
    }
    return nil
}

// ✅ Correct: country-scoped
func ApplyOffer(payment *Payment, offerCode string) error {
    if !dcs.IsEnabled("offers_engine", payment.Merchant.CountryCode) {
        return nil // Feature not enabled for this country
    }
    
    offer := fetchOffer(offerCode, payment.Merchant.CountryCode)
    if offer != nil && offer.IsValid() {
        payment.Discount = offer.CalculateDiscount(payment.Amount)
    }
    return nil
}
```

### 5. Fail-Safe by Default

Missing geo context = reject, not guess.

```go
// ❌ Anti-pattern: assume country
if country == "" {
    country = "IN" // Dangerous!
}

// ❌ Anti-pattern: guess variant on error
variant, err := splitz.Evaluate("experiment", context)
if err != nil {
    variant = "treatment" // Dangerous!
}

// ✅ Correct: reject if missing
if country == "" {
    return errors.New("country_code is required")
}

// ✅ Correct: fail to control
if err != nil {
    return "control" // Safe default
}
```

---

## Observability Principles

### Observe Geographically

Country dimension in all logs, metrics, traces.

```go
// ❌ Anti-pattern: no country context
logger.Info("payment created", "payment_id", paymentID)
metrics.PaymentCreated.Inc()

// ✅ Correct: country in all telemetry
logger.Info("payment created",
    "payment_id", paymentID,
    "country", merchant.CountryCode,
    "currency", payment.Currency,
)

metrics.PaymentCreated.WithLabelValues(
    merchant.CountryCode,
    payment.Currency,
).Inc()
```

### Structured Logging

```go
type PaymentLog struct {
    Event      string `json:"event"`
    PaymentID  string `json:"payment_id"`
    MerchantID string `json:"merchant_id"`
    Country    string `json:"country"`     // Always include
    Currency   string `json:"currency"`    // Always include
    Amount     int64  `json:"amount"`
    Timestamp  string `json:"timestamp"`
}
```

### Metrics with Country Labels

```go
var (
    PaymentCreated = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "payment_created_total",
            Help: "Total payments created",
        },
        []string{"country", "currency", "status"},
    )
    
    PaymentLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "payment_latency_seconds",
            Help:    "Payment processing latency",
            Buckets: prometheus.DefBuckets,
        },
        []string{"country", "payment_method"},
    )
)
```

---

## Testing Principles

### Test Multi-Nationally

```go
// ❌ Anti-pattern: single-country test data
func TestPaymentValidation(t *testing.T) {
    payment := Payment{
        Amount:   100,
        Currency: "INR",
        Country:  "IN",
    }
    assert.NoError(t, Validate(payment))
}

// ✅ Correct: parameterized multi-country tests
func TestPaymentValidation(t *testing.T) {
    testCases := []struct {
        name     string
        country  string
        currency string
        amount   int64
        wantErr  bool
    }{
        {"India valid", "IN", "INR", 100, false},
        {"India below min", "IN", "INR", 50, true},
        {"Malaysia valid", "MY", "MYR", 100, false},
        {"Malaysia below min", "MY", "MYR", 50, true},
        {"Singapore valid", "SG", "SGD", 100, false},
    }
    
    for _, tc := range testCases {
        t.Run(tc.name, func(t *testing.T) {
            payment := Payment{
                Amount:   tc.amount,
                Currency: tc.currency,
                Country:  tc.country,
            }
            err := Validate(payment)
            if tc.wantErr {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

### Test Data per Country

```json
// testdata/payments_in.json
{
    "country": "IN",
    "currency": "INR",
    "phone": "+919876543210",
    "postal_code": "560001"
}

// testdata/payments_my.json
{
    "country": "MY",
    "currency": "MYR",
    "phone": "+60123456789",
    "postal_code": "50000"
}
```

---

## Database Patterns

### Unicode Support

```sql
-- PostgreSQL (UTF-8 by default)
CREATE TABLE merchants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL, -- Supports Unicode
    country_code VARCHAR(2) NOT NULL
);

-- MySQL (explicit charset)
CREATE TABLE merchants (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) CHARACTER SET utf8mb4 NOT NULL,
    country_code VARCHAR(2) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Timestamps

```sql
-- Always use TIMESTAMP WITH TIME ZONE
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Country as Required Column

```sql
-- Every entity should have country context
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    merchant_id BIGINT NOT NULL,
    country_code VARCHAR(2) NOT NULL, -- Required for filtering/analytics
    amount_minor_units BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for country-based queries
CREATE INDEX idx_payments_country ON payments(country_code, created_at);
```

---

## Anti-Pattern Summary

| Category | Anti-Pattern | Correct Pattern |
|----------|--------------|-----------------|
| Country | `if country == "IN"` | `geoSDK.GetConfig(country)` |
| Country | Assume default country | Reject if missing |
| Currency | `"₹" + amount` | `i18nify.Format(amount, currency, locale)` |
| Currency | `amount * 100` | `currency.ConvertToMinorUnit(amount, currency)` |
| Timezone | `time.LoadLocation("Asia/Kolkata")` | `timezone.GetTimezone(country)` |
| DateTime | Store IST | Store UTC, display localized |
| Phone | Hardcoded `+91` | `phone.Parse(number, country)` |
| Phone | Separate fields | Single E.164 field |
| Feature | Global flag | Country-scoped flag |
| Feature | Assume treatment | Fail to control |
| Logging | No country in logs | Country in all logs |
| Metrics | No country label | Country label on all metrics |
| Testing | Single country data | Multi-country test cases |
| Branding | Hardcoded name | From Org entity via DCS |

---

## Checklist for New Features

- [ ] Country sourced from Account Service
- [ ] No hardcoded country/currency/timezone
- [ ] i18nify used for formatting
- [ ] GeoSDK used for business rules
- [ ] DCS used for feature flags (country-level)
- [ ] Timestamps stored as UTC
- [ ] Phone stored as E.164
- [ ] Currency stored as minor units
- [ ] Logs include country dimension
- [ ] Metrics include country label
- [ ] Database supports Unicode
- [ ] Multi-country test cases
- [ ] Error handling when country missing
- [ ] User-facing text externalized
