---
name: i18n-comprehensive
description: Comprehensive internationalization (i18n) skill for both detecting violations in code reviews AND generating i18n-ready code. Use for PR reviews to identify hardcoded currencies, regions, dates, payment methods, and localization issues. Also use when building new features, services, or components that need multi-region support (IN, MY, SG, US, etc.). Triggers on code review requests OR code generation involving regions, currencies, localization, or international support.
license: Complete terms in LICENSE.txt
---

# Comprehensive i18n Skill

A dual-purpose i18n skill combining **anomaly detection** for code reviews and **code generation** for building i18n-ready features.

## Two Operating Modes

### Mode 1: Anomaly Detection (Code Review)
Detect i18n violations in existing code during PR reviews.

### Mode 2: Code Builder (Feature Development)
Generate production-ready, i18n-compliant code following Razorpay's **Think Global, Build Once** principles.

---

## Part A: i18n Anomaly Detection

### Purpose

Detect code patterns that prevent international adoption:
- Hardcoded currencies, regions, timezones, date formats
- Missing localization for UI text, error messages
- Region-specific payment methods, phone formats, address assumptions
- Character encoding issues (non-UTF8, ASCII assumptions)

### Usage as i18n-Analyzer Sub-Agent

This operates with built-in quality filters:

- ✅ **Focus**: ONLY I18N category issues
- ✅ **Importance**: >= 7 (on 1-10 scale)
- ✅ **Confidence**: >= 80%
- ✅ **Verification**: Uses codebase access to verify issues before outputting

### Detection Quick Start

1. **Read the system prompt**: [references/prompt.toml](references/prompt.toml)
   - Complete role definition, category focus, quality thresholds, examples
   - Recommended i18n utilities and analysis workflow

2. **Review detection rules**: [references/detection-rules.md](references/detection-rules.md)
   - Comprehensive detection patterns for all i18n categories
   - Search strategies and importance classification

3. **Check language patterns**: [references/language-patterns.md](references/language-patterns.md)
   - Language-specific detection patterns (JS/TS, Python, Java, Go, React)

### I18N Categories

#### Critical (importance: 9-10)
- **Currency** - Hardcoded symbols, exchange rates
- **Region** - Country codes, regional assumptions
- **Timezone** - Fixed timezones, missing user timezone
- **Payment** - Region-specific payment methods
- **DateTime** - Hardcoded formats (MM/DD/YYYY)
- **Encoding** - ASCII assumptions, non-UTF8
- **Language** - Hardcoded text, missing i18n keys

#### Significant (importance: 8)
- Hardcoded region codes in business logic
- Date format assumptions without locale support
- Payment method restrictions by country
- Missing timezone handling in scheduling

#### Important (importance: 7)
- **Phone** - Fixed formats, country codes
- **Postal** - Hardcoded postal validation
- **Address** - Fixed address formats
- **Name** - First/last name assumptions
- **Units** - Metric vs imperial
- **FeatureFlags** - Missing region-based flags

### Detection Output Format

YAML format with verified i18n issues:

```yaml
suggestions:
  - file: path/to/file.js
    line: 42
    line_end: 45
    description: "Hardcoded USD symbol prevents international payments. Use Intl.NumberFormat."
    existing_code: |
      const price = '$' + amount.toFixed(2);
    suggestion_code: |
      const price = new Intl.NumberFormat(locale, {
        style: 'currency', currency: userCurrency
      }).format(amount);
    importance: 10
    confidence: 0.95
```

**Required fields**: file, line, description, importance, confidence
**Optional fields**: line_end, existing_code, suggestion_code

### Quality Controls

Before outputting any suggestion:
- ✅ Is this truly an i18n issue? (not bug/performance/security)
- ✅ Importance >= 7? (focus on important and critical issues)
- ✅ Confidence >= 80%? (high certainty)
- ✅ Verified using codebase access? (not assumptions)
- ✅ Working code fix provided? (actionable)
- ✅ Uses appropriate i18n utilities? (proper solution)

If all checks pass, output the suggestion. Otherwise, skip it.

---

## Part B: i18n Code Builder

### Core Philosophy

**Parameterize, Don't Hardcode** - Code should never "know" its country—it should be told via parameters.

**Externalize & Centralize** - Region-specific logic lives in config (DCS), not code.

**Fail-Safe by Default** - Missing geo context = reject or use safe defaults, never guess.

### Code Generation Quick Start

When generating code:

1. **Identify i18n dimensions** → Which aspects need internationalization?
2. **Use correct libraries** → i18nify, GeoSDK, DCS
3. **Apply patterns** → From `references/` files
4. **Validate** → No hardcoded country logic, proper error handling

### Razorpay i18n Stack

| Purpose | Library/Service | Usage |
|---------|-----------------|-------|
| Currency, Phone, DateTime, Names, Locale | **i18nify** | `github.com/razorpay/i18nify` |
| Razorpay country utilities | **GeoSDK** | `goutils/geosdk` |
| Feature configs per country | **DCS** | Dynamic Config Service |
| Merchant/Customer country | **Account Service** | Source of truth for country_code |
| Org branding | **Org Entity** | Brand names, logos, colors |

### Code Generation Interaction Flow

#### Phase 1: Requirements Gathering

Ask targeted questions:

```
To build i18n-ready code for [FEATURE], I need to understand:

1. **Target regions**: Which regions? (IN, MY, SG, US)
2. **i18n dimensions**: Which need handling?
   - Currency (use i18nify)
   - Phone numbers (use i18nify, store E.164)
   - DateTime/Timezone (use i18nify, store UTC)
   - Addresses (flexible schema)
   - User-facing text (externalize strings)
   - Feature flags (DCS, region-level)

3. **Language/framework**: Go, TypeScript, React?
4. **Country source**: Merchant country or customer country?
```

#### Phase 2: Generate Code

Apply patterns from references:

| Dimension | Reference File |
|-----------|---------------|
| Currency | `references/currency.md` |
| Phone | `references/phone.md` |
| DateTime/Timezone | `references/datetime.md` |
| Region/Config | `references/region.md` |
| Address | `references/address.md` |
| Language/Text | `references/language.md` |
| Feature Flags | `references/feature-flags.md` |
| Best Practices | `references/best-practices.md` |

### Golden Rules

#### 1. Never Hardcode Country Logic

```go
// ❌ NEVER
if country == "IN" {
    minAmount = 100
} else if country == "MY" {
    minAmount = 1
}

// ✅ ALWAYS
minAmount := geoSDK.GetMinimumAmount(merchant.CountryCode, currency)
```

#### 2. Country Comes from Account Service

```go
// ❌ NEVER
country := os.Getenv("DEFAULT_COUNTRY")
country := "IN" // hardcoded

// ✅ ALWAYS
country := merchant.GetCountryCode() // from Account Service
country := customer.GetCountryCode()
```

#### 3. Store Canonical, Display Localized

```go
// Storage: UTC, minor units, E.164
payment := Payment{
    AmountMinorUnits: 10000,        // Store in minor units
    Currency:         "MYR",         // ISO 4217
    CreatedAt:        time.Now().UTC(), // Always UTC
    Phone:            "+60123456789",   // E.164 format
}

// Display: Localized via i18nify
displayAmount := i18nify.FormatCurrency(payment.AmountMinorUnits, payment.Currency, locale)
displayTime := i18nify.FormatDateTime(payment.CreatedAt, merchant.Timezone)
```

#### 4. Feature Flags at Region Level

```go
// ❌ NEVER - global feature without country check
if featureFlags.IsEnabled("new_checkout") {
    return newCheckout(ctx)
}

// ✅ ALWAYS - country-scoped
if featureFlags.IsEnabled("new_checkout", merchant.CountryCode) {
    return newCheckout(ctx)
}
```

#### 5. Fail-Safe When Context Missing

```go
// ❌ NEVER - assume country
if country == "" {
    country = "IN" // dangerous!
}

// ✅ ALWAYS - reject or return error
if country == "" {
    return errors.New("country_code is required")
}
```

#### 6. Observe Geographically

```go
// ❌ NEVER - logs without country
logger.Info("payment created", "payment_id", paymentID)

// ✅ ALWAYS - include country dimension
logger.Info("payment created",
    "payment_id", paymentID,
    "country", merchant.CountryCode,
    "currency", payment.Currency)

// Metrics with country label
metrics.PaymentCreated.WithLabelValues(merchant.CountryCode, payment.Currency).Inc()
```

### Code Generation Checklist

Before delivering generated code, verify:

- [ ] No hardcoded country codes (`"IN"`, `"MY"`, `"SG"`)
- [ ] No hardcoded currency codes or symbols (`"INR"`, `"₹"`)
- [ ] No hardcoded timezone names (`"Asia/Kolkata"`, `"IST"`)
- [ ] Country sourced from Account Service (merchant/customer)
- [ ] i18nify used for currency, phone, datetime, names
- [ ] DCS used for feature flags (region-level toggle)
- [ ] Timestamps stored as UTC
- [ ] Phone numbers stored as E.164
- [ ] Currency amounts stored as minor units
- [ ] All logs/metrics include country dimension
- [ ] Proper error handling when country missing
- [ ] Database columns support Unicode (UTF-8)
- [ ] User-facing text externalized (not hardcoded strings)

---

## Key Principles (Both Modes)

1. **ONLY I18N** - Do not analyze bugs, performance, security, code quality, style, or tests
2. **Verify First** - Read files, search for existing i18n utilities, confirm issue is real
3. **High Quality** - Only output issues meeting importance/confidence thresholds (detection mode)
4. **Actionable** - Provide complete working code fixes with i18n utilities
5. **No Assumptions** - If uncertain about category, do not output
6. **Think Global, Build Once** - Code works everywhere from day one

## Example: Code Generation Session

**User**: Build a payment validation function for multi-region

**Claude**: I'll build an i18n-ready payment validator. Let me confirm:

1. Target regions: IN, MY, SG?
2. What validations needed: amount limits, currency, phone?
3. Country source: merchant country from Account Service?

**User**: Yes, all of that

**Claude**: Here's the i18n-ready implementation:

```go
package payment

import (
    "context"
    "fmt"

    "github.com/razorpay/i18nify-go/currency"
    "github.com/razorpay/i18nify-go/phone"
    "github.com/razorpay/goutils/geosdk"
    "github.com/razorpay/dcs"
)

type PaymentRequest struct {
    AmountMinorUnits int64
    Currency         string
    Phone            string
    MerchantID       string
}

type Validator struct {
    geoSDK  *geosdk.Client
    dcs     *dcs.Client
    account *account.Service
}

func (v *Validator) Validate(ctx context.Context, req PaymentRequest) error {
    // Get country from Account Service (never hardcode)
    merchant, err := v.account.GetMerchant(ctx, req.MerchantID)
    if err != nil {
        return fmt.Errorf("failed to get merchant: %w", err)
    }

    country := merchant.GetCountryCode()
    if country == "" {
        return errors.New("merchant country_code is required")
    }

    // Validate currency using i18nify
    if !currency.IsValid(req.Currency) {
        return fmt.Errorf("invalid currency: %s", req.Currency)
    }

    // Get min amount from GeoSDK (not hardcoded)
    minAmount := v.geoSDK.GetMinimumAmount(country, req.Currency)
    if req.AmountMinorUnits < minAmount {
        return fmt.Errorf("amount below minimum %d for %s", minAmount, country)
    }

    // Validate phone using i18nify
    if req.Phone != "" {
        if !phone.IsValidE164(req.Phone, country) {
            return fmt.Errorf("invalid phone format for %s", country)
        }
    }

    // Check feature flag at region level
    if !v.dcs.IsEnabled("payments_enabled", country) {
        return fmt.Errorf("payments not enabled for %s", country)
    }

    return nil
}
```

This follows all i18n principles:
- Country from Account Service ✓
- i18nify for currency/phone validation ✓
- GeoSDK for region-specific limits ✓
- DCS for feature flags at region level ✓
- Proper error handling when context missing ✓

## References

| File | Purpose |
|------|---------|
| [references/prompt.toml](references/prompt.toml) | **Main system prompt** - Complete sub-agent configuration for detection |
| [references/detection-rules.md](references/detection-rules.md) | Detection patterns and search strategies |
| [references/language-patterns.md](references/language-patterns.md) | Language-specific detection patterns |
| [references/currency.md](references/currency.md) | Currency handling patterns and best practices |
| [references/phone.md](references/phone.md) | Phone number validation and formatting |
| [references/datetime.md](references/datetime.md) | DateTime/Timezone handling |
| [references/region.md](references/region.md) | Region/Config management |
| [references/address.md](references/address.md) | Address format handling |
| [references/language.md](references/language.md) | Language/Text localization |
| [references/feature-flags.md](references/feature-flags.md) | Feature flag patterns |
| [references/best-practices.md](references/best-practices.md) | Comprehensive i18n best practices |

**See [references/prompt.toml](references/prompt.toml) for complete documentation, examples, and workflow.**
