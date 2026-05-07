# Address Patterns

## No Existing Utility

Razorpay does not have a dedicated address utility. Follow industry standard patterns.

## Core Principle

**Avoid Western assumptions** - not all countries have states, ZIP codes, or same address structure.

## Flexible Address Schema

```go
// ✅ Flexible schema that works globally
type Address struct {
    // Required fields
    Line1      string `json:"line1" validate:"required"`      // Street address
    City       string `json:"city" validate:"required"`       // City/town
    Country    string `json:"country" validate:"required"`    // ISO 3166-1 alpha-2

    // Optional fields (country-dependent)
    Line2      string `json:"line2,omitempty"`                // Apt, suite, etc.
    State      string `json:"state,omitempty"`                // State/province/region
    PostalCode string `json:"postal_code,omitempty"`          // ZIP/postal code
    District   string `json:"district,omitempty"`             // For countries that use districts
}
```

## Anti-Patterns

```go
// ❌ NEVER - Western-centric required fields
type Address struct {
    Street    string `validate:"required"`
    City      string `validate:"required"`
    State     string `validate:"required"`  // Not all countries have states
    ZipCode   string `validate:"required,len=5"` // US-specific
    Country   string `validate:"required"`
}

// ❌ NEVER - hardcoded postal code validation
if len(postalCode) != 5 {
    return errors.New("invalid ZIP code")
}

// ✅ ALWAYS - country-specific validation
if err := validatePostalCode(postalCode, country); err != nil {
    return err
}
```

## Country-Specific Postal Code Patterns

```go
var postalCodePatterns = map[string]*regexp.Regexp{
    "IN": regexp.MustCompile(`^\d{6}$`),           // India: 6 digits
    "MY": regexp.MustCompile(`^\d{5}$`),           // Malaysia: 5 digits
    "SG": regexp.MustCompile(`^\d{6}$`),           // Singapore: 6 digits
    "US": regexp.MustCompile(`^\d{5}(-\d{4})?$`),  // US: 5 or 9 digits
    "UK": regexp.MustCompile(`^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$`), // UK
}

func ValidatePostalCode(postalCode, country string) error {
    pattern, ok := postalCodePatterns[country]
    if !ok {
        // No specific validation for this country
        return nil
    }
    
    if !pattern.MatchString(postalCode) {
        return fmt.Errorf("invalid postal code format for %s", country)
    }
    return nil
}
```

## Address Validation

```go
func ValidateAddress(addr Address) error {
    // Required fields for all countries
    if addr.Line1 == "" {
        return errors.New("address line1 is required")
    }
    if addr.City == "" {
        return errors.New("city is required")
    }
    if addr.Country == "" {
        return errors.New("country is required")
    }
    
    // Country-specific validations
    switch addr.Country {
    case "US":
        if addr.State == "" {
            return errors.New("state is required for US addresses")
        }
        if addr.PostalCode == "" {
            return errors.New("ZIP code is required for US addresses")
        }
    case "IN":
        if addr.PostalCode == "" {
            return errors.New("PIN code is required for Indian addresses")
        }
    }
    
    // Postal code format validation
    if addr.PostalCode != "" {
        if err := ValidatePostalCode(addr.PostalCode, addr.Country); err != nil {
            return err
        }
    }
    
    return nil
}
```

## Database Schema

```sql
CREATE TABLE addresses (
    id BIGSERIAL PRIMARY KEY,
    line1 VARCHAR(255) NOT NULL,
    line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),           -- Optional
    postal_code VARCHAR(20),      -- Variable length
    district VARCHAR(100),        -- For countries using districts
    country VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2
    
    -- Unicode support for international characters
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure UTF-8 for international characters
-- (PostgreSQL default, MySQL needs explicit charset)
```

## Display Formatting

Different countries have different address display formats:

```go
func FormatAddressForDisplay(addr Address) string {
    switch addr.Country {
    case "US":
        // US: Street, City, State ZIP
        return fmt.Sprintf("%s\n%s, %s %s", 
            addr.Line1, addr.City, addr.State, addr.PostalCode)
    case "IN":
        // India: Street, City - PIN, State
        return fmt.Sprintf("%s\n%s - %s\n%s", 
            addr.Line1, addr.City, addr.PostalCode, addr.State)
    case "MY":
        // Malaysia: Street, PostalCode City, State
        return fmt.Sprintf("%s\n%s %s\n%s", 
            addr.Line1, addr.PostalCode, addr.City, addr.State)
    default:
        // Generic format
        parts := []string{addr.Line1}
        if addr.Line2 != "" {
            parts = append(parts, addr.Line2)
        }
        cityLine := addr.City
        if addr.PostalCode != "" {
            cityLine = fmt.Sprintf("%s %s", addr.PostalCode, addr.City)
        }
        parts = append(parts, cityLine)
        if addr.State != "" {
            parts = append(parts, addr.State)
        }
        return strings.Join(parts, "\n")
    }
}
```

## API Request/Response

```go
// API accepts flexible address structure
type CreateMerchantRequest struct {
    Name    string  `json:"name"`
    Address Address `json:"address"`
}

// Validation based on country
func (r *CreateMerchantRequest) Validate() error {
    return ValidateAddress(r.Address)
}
```
