# Code Smells Reference Guide

A comprehensive guide to identifying and addressing common code smells during code reviews.

## What is a Code Smell?

A code smell is a surface indication that usually corresponds to a deeper problem in the system. Code smells are not bugs—they are not technically incorrect and don't prevent the program from functioning. Instead, they indicate weaknesses in design that may slow down development or increase the risk of bugs or failures in the future.

## Categories of Code Smells

### 1. Bloaters

Code, methods, and classes that have increased to such gargantuan proportions that they're hard to work with.

#### Long Method
**Problem:** A method contains too many lines of code (generally > 50 lines).

**Impact:**
- Hard to understand and maintain
- Difficult to test
- Usually doing too many things

**Detection:**
```python
# ❌ Code Smell: Long Method (100+ lines)
def process_order(order_data):
    # Validate data
    if not order_data.get('customer_id'):
        raise ValueError("Missing customer")
    if not order_data.get('items'):
        raise ValueError("Missing items")
    # ... 20 more validation lines

    # Calculate totals
    subtotal = 0
    for item in order_data['items']:
        subtotal += item['price'] * item['quantity']
    # ... 20 more calculation lines

    # Apply discounts
    # ... 20 lines of discount logic

    # Process payment
    # ... 20 lines of payment logic

    # Send notifications
    # ... 20 lines of notification logic
```

**Solution:** Extract Method
```python
# ✅ Fixed: Multiple focused methods
def process_order(order_data):
    validate_order(order_data)
    totals = calculate_order_totals(order_data)
    apply_discounts(totals, order_data)
    process_payment(totals)
    send_order_notifications(order_data)

def validate_order(order_data):
    if not order_data.get('customer_id'):
        raise ValueError("Missing customer")
    if not order_data.get('items'):
        raise ValueError("Missing items")

def calculate_order_totals(order_data):
    # Focused calculation logic
    pass
```

#### Large Class (God Object)
**Problem:** A class tries to do too much and has too many responsibilities.

**Signs:**
- 20+ methods
- 10+ instance variables
- Difficult to name without "And" or "Manager"
- Violates Single Responsibility Principle

**Solution:** Extract Class, Extract Subclass

#### Long Parameter List
**Problem:** A function has more than 3-4 parameters.

**Impact:**
- Hard to understand what each parameter does
- Easy to pass parameters in wrong order
- Changes require updating many call sites

**Detection:**
```python
# ❌ Code Smell: Long Parameter List
def create_user(username, password, email, first_name, last_name,
                phone, address, city, state, zip_code, country):
    pass
```

**Solution:** Introduce Parameter Object
```python
# ✅ Fixed: Parameter Object
@dataclass
class UserInfo:
    username: str
    password: str
    email: str
    first_name: str
    last_name: str
    contact: ContactInfo
    address: Address

def create_user(user_info: UserInfo):
    pass
```

#### Data Clumps
**Problem:** Same group of variables appears together in multiple places.

**Example:**
```python
# ❌ Code Smell: Data Clumps
def calculate_distance(x1, y1, x2, y2):
    pass

def draw_line(x1, y1, x2, y2):
    pass
```

**Solution:**
```python
# ✅ Fixed: Extract Class
@dataclass
class Point:
    x: float
    y: float

def calculate_distance(point1: Point, point2: Point):
    pass

def draw_line(start: Point, end: Point):
    pass
```

### 2. Object-Orientation Abusers

Incorrect or incomplete application of object-oriented programming principles.

#### Switch Statements (Polymorphism Alternative)
**Problem:** Complex switch/case or if-elif chains based on object type.

**Detection:**
```python
# ❌ Code Smell: Type Checking
def calculate_area(shape):
    if shape.type == 'circle':
        return math.pi * shape.radius ** 2
    elif shape.type == 'rectangle':
        return shape.width * shape.height
    elif shape.type == 'triangle':
        return 0.5 * shape.base * shape.height
```

**Solution:** Use polymorphism
```python
# ✅ Fixed: Polymorphism
class Shape(ABC):
    @abstractmethod
    def calculate_area(self) -> float:
        pass

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius

    def calculate_area(self) -> float:
        return math.pi * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def calculate_area(self) -> float:
        return self.width * self.height
```

#### Refused Bequest
**Problem:** A subclass uses only some of the methods and properties inherited from its parents.

**Sign:** Subclass throws "not supported" exceptions for inherited methods.

**Solution:** Replace inheritance with delegation or create a different hierarchy.

#### Temporary Field
**Problem:** Instance variables that are only set in certain circumstances.

**Impact:**
- Confusing for readers
- Likely indicates poor design

**Solution:** Extract class for these fields or use method parameters.

### 3. Change Preventers

Changes in one place require many changes in other places.

#### Divergent Change
**Problem:** One class is commonly changed in different ways for different reasons.

**Example:** A User class that changes when:
- Authentication logic changes
- User profile requirements change
- Notification preferences change

**Solution:** Extract classes for each responsibility (SRP).

#### Shotgun Surgery
**Problem:** A single change requires making many small changes to many different classes.

**Impact:**
- High risk of missing a change
- Time-consuming modifications

**Solution:** Move Method and Move Field to consolidate changes.

### 4. Dispensables

Unnecessary code that should be removed.

#### Comments
**Problem:** Excessive or outdated comments that explain *what* the code does instead of *why*.

```python
# ❌ Code Smell: Obvious Comment
# Increment i by 1
i = i + 1

# Get the user by ID
user = get_user_by_id(user_id)
```

**When Comments Are Good:**
- Explain *why* a particular approach was chosen
- Document complex algorithms
- Warn about gotchas or non-obvious behavior
- Provide examples of usage

```python
# ✅ Good Comment
# Using exponential backoff because the API rate limits to 100 req/min
# and has been observed to have transient failures under load
retry_with_backoff(api_call)
```

#### Dead Code
**Problem:** Unused variables, parameters, methods, or classes.

**Impact:**
- Confuses readers
- Increases maintenance burden
- May cause confusion about intent

**Detection:**
- Commented-out code
- Unreachable code (after return/break)
- Unused imports
- Unused variables

**Solution:** Delete it! Version control preserves history.

#### Duplicate Code
**Problem:** Same code structure appears in multiple places.

**Types:**
1. **Exact Duplication:** Identical code in multiple locations
2. **Structural Duplication:** Similar structure with minor variations
3. **Conceptual Duplication:** Different code accomplishing same thing

**Solution:**
- Extract Method
- Pull Up Method (to superclass)
- Form Template Method

#### Lazy Class
**Problem:** A class doesn't do enough to justify its existence.

**Example:**
```python
# ❌ Code Smell: Lazy Class
class EmailValidator:
    def validate(self, email: str) -> bool:
        return '@' in email  # That's it?
```

**Solution:** Inline the class or expand its responsibilities if justified.

#### Speculative Generality
**Problem:** Code written to handle future scenarios that may never happen.

**Signs:**
- Unused abstract classes
- Overly complex framework
- Parameters that are never used
- Unusual test method names

**Solution:** Remove the unused abstraction. YAGNI (You Aren't Gonna Need It).

### 5. Couplers

Excessive coupling between classes.

#### Feature Envy
**Problem:** A method accesses data of another object more than its own data.

**Detection:**
```python
# ❌ Code Smell: Feature Envy
class OrderProcessor:
    def calculate_total(self, order):
        total = 0
        for item in order.items:
            total += item.price * item.quantity
        total = total * (1 - order.discount)
        total = total * (1 + order.tax_rate)
        return total
```

**Solution:** Move the method to the class it's most interested in
```python
# ✅ Fixed: Move Method
class Order:
    def calculate_total(self):
        subtotal = sum(item.price * item.quantity for item in self.items)
        total = subtotal * (1 - self.discount)
        total = total * (1 + self.tax_rate)
        return total
```

#### Inappropriate Intimacy
**Problem:** Classes know too much about each other's internal details.

**Signs:**
- Accessing private fields of another class
- Bidirectional associations
- Lots of back-and-forth method calls

**Solution:**
- Move Method/Field
- Extract Class
- Hide Delegate

#### Message Chains
**Problem:** Long chains of method calls (Law of Demeter violation).

**Detection:**
```python
# ❌ Code Smell: Message Chain
customer_city = order.customer.address.city
manager_email = employee.department.manager.email
```

**Solution:** Hide Delegate
```python
# ✅ Fixed: Hide Delegate
customer_city = order.get_customer_city()
manager_email = employee.get_manager_email()

# In Order class:
def get_customer_city(self):
    return self.customer.get_city()
```

#### Middle Man
**Problem:** A class delegates most of its work to another class.

**Detection:** Class with many methods that just call methods on another class.

**Solution:** Remove the middle man, let clients call the delegate directly.

### 6. Naming Issues

Poor naming makes code hard to understand.

#### Mysterious Name
**Problem:** Variable, method, or class name doesn't clearly convey its purpose.

```python
# ❌ Code Smell: Mysterious Names
def calc(x, y):
    return x * y * 0.05

data = get_data()
temp = process(data)
result = temp.value
```

**Solution:**
```python
# ✅ Fixed: Intention-Revealing Names
def calculate_commission(sale_amount: float, quantity: int) -> float:
    COMMISSION_RATE = 0.05
    return sale_amount * quantity * COMMISSION_RATE

customer_orders = get_customer_orders()
validated_orders = validate_orders(customer_orders)
total_revenue = validated_orders.total_value
```

#### Magic Numbers
**Problem:** Numeric literals without explanation.

```python
# ❌ Code Smell: Magic Numbers
if user.age > 18 and user.score > 650:
    approve_loan(user)
```

**Solution:**
```python
# ✅ Fixed: Named Constants
MINIMUM_AGE = 18
MINIMUM_CREDIT_SCORE = 650

if user.age > MINIMUM_AGE and user.score > MINIMUM_CREDIT_SCORE:
    approve_loan(user)
```

### 7. Complexity Smells

#### Deep Nesting
**Problem:** Code with many levels of indentation.

**Impact:**
- Hard to follow logic
- Difficult to test
- High cognitive load

```python
# ❌ Code Smell: Deep Nesting
def process_user(user):
    if user is not None:
        if user.is_active:
            if user.has_permission('admin'):
                if user.last_login > threshold:
                    return process_admin(user)
                else:
                    return "Login required"
    return "Invalid user"
```

**Solution:** Use guard clauses
```python
# ✅ Fixed: Guard Clauses
def process_user(user):
    if user is None:
        return "Invalid user"

    if not user.is_active:
        return "Inactive user"

    if not user.has_permission('admin'):
        return "Insufficient permissions"

    if user.last_login <= threshold:
        return "Login required"

    return process_admin(user)
```

#### Complex Conditionals
**Problem:** Complex boolean expressions that are hard to understand.

```python
# ❌ Code Smell: Complex Conditional
if (user.age >= 18 and user.income > 30000) or \
   (user.age >= 21 and user.has_cosigner and user.income > 20000) or \
   (user.credit_score > 700 and user.employment_years > 2):
    approve_loan(user)
```

**Solution:** Extract Method
```python
# ✅ Fixed: Extracted Method
def is_eligible_for_loan(user):
    return (meets_standard_criteria(user) or
            meets_cosigner_criteria(user) or
            meets_excellent_credit_criteria(user))

def meets_standard_criteria(user):
    return user.age >= 18 and user.income > 30000

def meets_cosigner_criteria(user):
    return (user.age >= 21 and
            user.has_cosigner and
            user.income > 20000)

def meets_excellent_credit_criteria(user):
    return (user.credit_score > 700 and
            user.employment_years > 2)

if is_eligible_for_loan(user):
    approve_loan(user)
```

## Language-Specific Smells

### Python-Specific

#### Mutable Default Arguments
```python
# ❌ Code Smell
def add_item(item, items=[]):
    items.append(item)
    return items

# ✅ Fixed
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

#### Not Using Context Managers
```python
# ❌ Code Smell
f = open('file.txt')
data = f.read()
f.close()

# ✅ Fixed
with open('file.txt') as f:
    data = f.read()
```

### JavaScript-Specific

#### Callback Hell
```javascript
// ❌ Code Smell
getData(function(a) {
    getMoreData(a, function(b) {
        getMoreData(b, function(c) {
            getMoreData(c, function(d) {
                // ...
            });
        });
    });
});

// ✅ Fixed: Async/Await
async function processData() {
    const a = await getData();
    const b = await getMoreData(a);
    const c = await getMoreData(b);
    const d = await getMoreData(c);
}
```

## Detection Strategy

When reviewing code, systematically check for:

1. **Size Issues**
   - Methods > 50 lines
   - Classes > 300 lines
   - Parameter lists > 3-4 parameters
   - Nesting depth > 3 levels

2. **Naming Issues**
   - Vague names (data, temp, result)
   - Type in name (userList, stringValue)
   - Abbreviations (usr, ctx, msg)

3. **Structure Issues**
   - Duplicate code blocks
   - Long if-elif chains
   - Complex boolean expressions
   - Many dependencies

4. **Responsibility Issues**
   - Classes doing too much
   - Methods doing too much
   - Mixed abstraction levels

## Refactoring Catalog

Common refactoring techniques to address code smells:

1. **Extract Method**: Break long methods into smaller ones
2. **Extract Class**: Pull out responsibilities into new class
3. **Inline**: Merge trivial methods/classes
4. **Move Method/Field**: Move to appropriate class
5. **Replace Conditional with Polymorphism**: Use inheritance instead of type checking
6. **Introduce Parameter Object**: Group related parameters
7. **Replace Magic Number with Constant**: Name literal values
8. **Decompose Conditional**: Extract complex conditions into methods
9. **Consolidate Duplicate Conditional Fragments**: Remove duplication

## Tools

Automated tools to detect code smells:

### Python
- **pylint**: Comprehensive linting
- **radon**: Cyclomatic complexity
- **vulture**: Dead code detection
- **pyflakes**: Unused imports/variables

### JavaScript
- **ESLint**: Code quality and patterns
- **SonarJS**: Code smells and complexity
- **jscpd**: Duplicate code detection

### Java
- **PMD**: Code quality
- **Checkstyle**: Style and patterns
- **SpotBugs**: Bug patterns

### General
- **SonarQube**: Multi-language code quality
- **CodeClimate**: Automated code review

## References

- Martin Fowler's "Refactoring: Improving the Design of Existing Code"
- Robert C. Martin's "Clean Code"
- [Refactoring Guru - Code Smells](https://refactoring.guru/refactoring/smells)
