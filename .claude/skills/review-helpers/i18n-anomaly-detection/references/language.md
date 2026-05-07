# Language & Text Patterns

## No Existing Translator

Razorpay does not have a dedicated translation service. Follow industry best practices.

## Core Principle

**Externalize all user-facing text** - never hardcode strings in code.

## Pattern: Translation Keys

Use keys that map to translated strings:

```go
// ❌ NEVER - hardcoded strings
return errors.New("Payment failed. Please try again.")

// ✅ ALWAYS - translation keys
return NewLocalizedError("payment.failed.retry")
```

## Go Implementation

### Error Handling

```go
// Localized error type
type LocalizedError struct {
    Code       string            // Machine-readable: "PAYMENT_FAILED"
    MessageKey string            // i18n key: "errors.payment.failed"
    Params     map[string]string // For interpolation
}

func (e *LocalizedError) Error() string {
    return e.Code
}

// Create localized errors
func NewPaymentError(code, messageKey string, params map[string]string) *LocalizedError {
    return &LocalizedError{
        Code:       code,
        MessageKey: messageKey,
        Params:     params,
    }
}

// Usage
func ValidateAmount(amount int64, minAmount int64, currency string) error {
    if amount < minAmount {
        return NewPaymentError(
            "AMOUNT_TOO_LOW",
            "errors.payment.amount_below_minimum",
            map[string]string{
                "minimum":  formatCurrency(minAmount, currency),
                "currency": currency,
            },
        )
    }
    return nil
}
```

### Translation File Structure

```yaml
# translations/en.yaml
errors:
  payment:
    failed: "Payment failed. Please try again."
    amount_below_minimum: "Amount must be at least {{minimum}}"
    invalid_currency: "Currency {{currency}} is not supported"
  validation:
    required: "{{field}} is required"
    invalid_format: "Invalid {{field}} format"

messages:
  payment:
    success: "Payment of {{amount}} was successful"
    processing: "Processing your payment..."

# translations/ms.yaml (Malay)
errors:
  payment:
    failed: "Pembayaran gagal. Sila cuba lagi."
    amount_below_minimum: "Jumlah mestilah sekurang-kurangnya {{minimum}}"
```

### Translation Loader

```go
type Translator struct {
    translations map[string]map[string]string // locale -> key -> value
}

func NewTranslator(translationsDir string) *Translator {
    t := &Translator{
        translations: make(map[string]map[string]string),
    }
    // Load translations from files
    t.loadTranslations(translationsDir)
    return t
}

func (t *Translator) Translate(locale, key string, params map[string]string) string {
    // Get translation for locale
    localeTranslations, ok := t.translations[locale]
    if !ok {
        // Fallback to English
        localeTranslations = t.translations["en"]
    }
    
    template, ok := localeTranslations[key]
    if !ok {
        // Return key if translation missing
        return key
    }
    
    // Interpolate params
    result := template
    for k, v := range params {
        result = strings.ReplaceAll(result, "{{"+k+"}}", v)
    }
    
    return result
}
```

## JavaScript/React Implementation

```javascript
// translations/en.json
{
  "errors": {
    "payment": {
      "failed": "Payment failed. Please try again.",
      "amount_below_minimum": "Amount must be at least {{minimum}}"
    }
  },
  "buttons": {
    "submit": "Submit",
    "cancel": "Cancel",
    "pay_now": "Pay Now"
  }
}

// Using react-i18next
import { useTranslation } from 'react-i18next';

function PaymentButton({ amount, currency }) {
    const { t } = useTranslation();
    
    return (
        <button>
            {t('buttons.pay_now')} - {formatCurrency(amount, currency)}
        </button>
    );
}

function ErrorMessage({ error }) {
    const { t } = useTranslation();
    
    return (
        <div className="error">
            {t(error.messageKey, error.params)}
        </div>
    );
}
```

## Anti-Patterns

```go
// ❌ NEVER - hardcoded user-facing strings
return errors.New("Payment failed. Please try again.")
fmt.Sprintf("Hello, %s! Your order is confirmed.", name)
logger.Error("Something went wrong") // if shown to user

// ❌ NEVER - string concatenation for messages
message := "Hello, " + name + "! Your order #" + orderID + " is confirmed."

// ❌ NEVER - inline text in templates
<button>Submit Payment</button>
<span>Processing...</span>

// ✅ ALWAYS - translation keys
return NewLocalizedError("errors.payment.failed")
t.Translate(locale, "messages.order.confirmed", map[string]string{"name": name, "order_id": orderID})

// ✅ ALWAYS - translation keys in templates
<button>{t('buttons.submit_payment')}</button>
<span>{t('status.processing')}</span>
```

## API Error Responses

```go
// API error response with i18n support
type APIError struct {
    Code       string            `json:"code"`        // PAYMENT_FAILED
    Message    string            `json:"message"`     // English default
    MessageKey string            `json:"message_key"` // For client-side i18n
    Params     map[string]string `json:"params"`      // For interpolation
}

func NewAPIError(code, messageKey string, params map[string]string) *APIError {
    return &APIError{
        Code:       code,
        Message:    translator.Translate("en", messageKey, params), // Default English
        MessageKey: messageKey,
        Params:     params,
    }
}

// Usage
func handlePaymentError(w http.ResponseWriter, err error) {
    apiErr := NewAPIError(
        "PAYMENT_FAILED",
        "errors.payment.failed",
        nil,
    )
    
    w.WriteHeader(http.StatusBadRequest)
    json.NewEncoder(w).Encode(apiErr)
}
```

## Locale Detection

```go
// Get locale from merchant country
func GetLocaleForMerchant(merchant *Merchant) string {
    country := merchant.GetCountryCode()
    
    // Map country to locale
    locales := map[string]string{
        "IN": "en-IN",
        "MY": "en-MY", // or "ms-MY" for Malay
        "SG": "en-SG",
        "US": "en-US",
    }
    
    if locale, ok := locales[country]; ok {
        return locale
    }
    return "en" // Default
}
```

## Best Practices

1. **Use translation keys**, not hardcoded strings
2. **Separate user-facing from internal errors**
3. **Use parameterized messages** for dynamic content (ICU message format)
4. **Provide fallback** to default language (English)
5. **Include message_key in API responses** for client-side i18n
6. **Never concatenate strings** - breaks translation word order
7. **Handle pluralization** properly (1 item vs 2 items)
