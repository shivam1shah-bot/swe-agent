# Feature Flags Patterns

## System

**Always use DCS** (Dynamic Config Service) for feature flags.

## Core Principle

**Single flag, toggled at region level** - not separate flags per region.

```go
// ❌ NEVER - separate flags per country
dcs.IsEnabled("instant_settlements_india")
dcs.IsEnabled("instant_settlements_malaysia")

// ✅ ALWAYS - single flag, country parameter
dcs.IsEnabled("instant_settlements", merchant.GetCountryCode())
```

## DCS Usage

```go
import (
    "github.com/razorpay/dcs"
)

// Initialize
dcsClient := dcs.New()

// Check feature flag with country context
isEnabled := dcsClient.IsEnabled("new_checkout", map[string]interface{}{
    "country": merchant.GetCountryCode(),
})

// With additional context
isEnabled := dcsClient.IsEnabled("instant_settlements", map[string]interface{}{
    "country":     merchant.GetCountryCode(),
    "merchant_id": merchant.ID,
    "org_id":      merchant.OrgID,
})
```

## Feature Flag Patterns

### Basic Feature Check

```go
func ProcessPayment(ctx context.Context, merchant *Merchant, payment *Payment) error {
    // Feature flag check with country
    if !dcsClient.IsEnabled("new_payment_flow", merchant.GetCountryCode()) {
        return legacyPaymentFlow(ctx, payment)
    }
    return newPaymentFlow(ctx, payment)
}
```

### Feature + Experiment

```go
func EnableFeature(ctx context.Context, merchant *Merchant) (*Result, error) {
    country := merchant.GetCountryCode()
    
    // First: Check if feature is enabled for country
    if !dcsClient.IsEnabled("instant_settlements", country) {
        logger.Info("feature not enabled for country", "country", country)
        return &Result{
            Enabled: false,
            Reason:  "not_available_in_country",
        }, nil
    }
    
    // Second: Experiment evaluation with country context
    variant := splitz.Evaluate("instant_settlements_v2", map[string]interface{}{
        "merchant_id": merchant.ID,
        "country":     country,
        "cell_id":     merchant.CellID,
    })
    
    if variant == "treatment" {
        return &Result{Enabled: true, Variant: "treatment"}, nil
    }
    
    return &Result{Enabled: false, Variant: "control"}, nil
}
```

## Fail-Safe Defaults

**When country context is missing or evaluation fails, default to safe behavior:**

```go
func GetFeatureVariant(ctx context.Context, feature string, merchant *Merchant) string {
    country := merchant.GetCountryCode()
    
    // Fail-safe: reject if country missing
    if country == "" {
        logger.Warn("country missing, returning control")
        return "control"
    }
    
    // Fail-safe: return control on error
    variant, err := dcsClient.Evaluate(feature, map[string]interface{}{
        "country": country,
    })
    if err != nil {
        logger.Error("feature evaluation failed", "error", err)
        return "control" // Safe default
    }
    
    return variant
}
```

## Anti-Patterns

```go
// ❌ NEVER - global flag without country
if dcsClient.IsEnabled("new_checkout") {
    return newCheckout()
}

// ❌ NEVER - assume treatment on failure
variant, err := splitz.Evaluate("experiment", context)
if err != nil {
    variant = "treatment" // Dangerous!
}

// ❌ NEVER - hardcoded feature per country
if country == "IN" && featureEnabled {
    // India-specific feature
}

// ✅ ALWAYS - country-scoped flag
if dcsClient.IsEnabled("new_checkout", merchant.GetCountryCode()) {
    return newCheckout()
}

// ✅ ALWAYS - fail to control
if err != nil {
    variant = "control" // Safe default
}
```

## Rollout Strategy

1. **Enable for one country** (e.g., India)
2. **Validate for 2 weeks** - monitor metrics, logs
3. **Gradually enable for other countries**

```go
// DCS config example
// instant_settlements:
//   IN: true    # Week 1: India enabled
//   MY: false   # Week 3: Enable after India validation
//   SG: false   # Week 5: Enable after MY validation
```

## Logging Feature Flag Decisions

```go
func CheckFeature(ctx context.Context, feature string, merchant *Merchant) bool {
    country := merchant.GetCountryCode()
    isEnabled := dcsClient.IsEnabled(feature, country)
    
    // Always log feature flag decisions
    logger.Info("feature flag checked",
        "feature", feature,
        "country", country,
        "merchant_id", merchant.ID,
        "enabled", isEnabled,
    )
    
    return isEnabled
}
```

## Feature Flag Checklist

When implementing a new feature:

- [ ] Single flag name (not per-country flags)
- [ ] Country passed as parameter
- [ ] Fail-safe to disabled/control when context missing
- [ ] Logging of flag decisions with country context
- [ ] Rollout plan: enable one country at a time
- [ ] Metrics include country dimension
