# Region & Country Configuration Patterns

## Country Source

**Always get country from Account Service** - never hardcode or assume.

| Entity | Source |
|--------|--------|
| Merchant country | `merchant.GetCountryCode()` from Account Service |
| Customer country | `customer.GetCountryCode()` from customer data |
| Service region | Environment variable (which cell/region service runs in) |

## Configuration Sources

| Type | Source | Use Case |
|------|--------|----------|
| Static country data | **i18nify** | Currencies, formats, dial codes |
| Razorpay-specific country data | **GeoSDK** (goutils) | Min amounts, limits, features |
| Runtime feature config | **DCS** | Feature flags, toggles per country |
| Service deployment region | **Environment variable** | Which region the service instance runs in |

## GeoSDK Usage (goutils)

```go
import (
    "github.com/razorpay/goutils/geosdk"
)

// Initialize
geoClient := geosdk.New()

// Get minimum amount for country/currency
minAmount := geoClient.GetMinimumAmount("MY", "MYR") // 100 (1 MYR in sen)

// Get supported currencies for country
currencies := geoClient.GetSupportedCurrencies("MY") // ["MYR"]

// Get supported payment methods
methods := geoClient.GetPaymentMethods("MY") // ["fpx", "card", "duitnow"]

// Check if country is supported
isSupported := geoClient.IsCountrySupported("MY") // true

// Get tax rate
taxRate := geoClient.GetTaxRate("MY") // 0.06 (6% SST)
```

## DCS Feature Configuration

```go
import (
    "github.com/razorpay/dcs"
)

// Initialize DCS client
dcsClient := dcs.New()

// Check feature flag at country level
isEnabled := dcsClient.IsEnabled("instant_settlements", map[string]interface{}{
    "country": merchant.GetCountryCode(),
})

// Get config value for country
config := dcsClient.GetConfig("settlement_schedule", map[string]interface{}{
    "country": merchant.GetCountryCode(),
})
```

## i18nify for Static Country Data

```go
import (
    "github.com/razorpay/i18nify-go/country"
)

// Get country info
info := country.GetInfo("MY")
// {Name: "Malaysia", Currency: "MYR", Locale: "en-MY", ...}

// Get dial code
dialCode := country.GetDialCode("MY") // "+60"

// Get locale
locale := country.GetLocale("MY") // "en-MY"
```

## Anti-Patterns

```go
// ❌ NEVER - hardcoded country checks
if country == "IN" {
    minAmount = 100
} else if country == "MY" {
    minAmount = 100
}

// ❌ NEVER - org-based instead of geography-based
if merchant.OrgID == "curlec" {
    return "T+3" // Malaysian settlement
}

// ❌ NEVER - assume default country
if country == "" {
    country = "IN"
}

// ❌ NEVER - scattered constants
var TaxRates = map[string]float64{"IN": 18.0, "MY": 6.0}
var MinAmounts = map[string]int64{"INR": 100, "MYR": 100}

// ✅ ALWAYS - parameterized via GeoSDK/DCS
minAmount := geoClient.GetMinimumAmount(country, currency)
taxRate := geoClient.GetTaxRate(country)
isEnabled := dcsClient.IsEnabled("feature", country)
```

## Service Knowing Its Region

For a service to know which region/cell it's running in:

```go
// From environment variable
func GetServiceRegion() string {
    return os.Getenv("SERVICE_REGION") // "IN", "MY", "SG"
}

func GetServiceCell() string {
    return os.Getenv("CELL_ID") // "in-cell-1", "my-cell-1"
}
```

## Pattern: Region-Agnostic Service

```go
type PaymentService struct {
    geo    *geosdk.Client
    dcs    *dcs.Client
    account *account.Service
}

func (s *PaymentService) Process(ctx context.Context, req PaymentRequest) error {
    // 1. Get country from Account Service (never hardcode)
    merchant, err := s.account.GetMerchant(ctx, req.MerchantID)
    if err != nil {
        return err
    }
    
    country := merchant.GetCountryCode()
    if country == "" {
        return errors.New("merchant country_code is required")
    }
    
    // 2. Get region-specific config from GeoSDK
    minAmount := s.geo.GetMinimumAmount(country, req.Currency)
    if req.Amount < minAmount {
        return fmt.Errorf("amount below minimum for %s", country)
    }
    
    // 3. Check feature flag from DCS
    if !s.dcs.IsEnabled("payments_enabled", country) {
        return fmt.Errorf("payments not enabled for %s", country)
    }
    
    // 4. Process payment (same code for all countries)
    return s.processPayment(ctx, req, merchant)
}
```

## Configuration Hierarchy

```
1. DCS (runtime, dynamic)     → Feature flags, toggles
2. GeoSDK (Razorpay-specific) → Business rules, limits
3. i18nify (static, universal) → Formats, locale data
4. Environment (deployment)    → Service region/cell
```

## Multi-Region Deployment

```yaml
# Environment variables per deployment
# India cell
SERVICE_REGION: "IN"
CELL_ID: "in-cell-1"

# Malaysia cell
SERVICE_REGION: "MY"
CELL_ID: "my-cell-1"

# Singapore cell
SERVICE_REGION: "SG"
CELL_ID: "sg-cell-1"
```

Service code remains the same - behavior changes via:
- DCS configs (per country)
- GeoSDK data (per country)
- Merchant's country_code (per request)
