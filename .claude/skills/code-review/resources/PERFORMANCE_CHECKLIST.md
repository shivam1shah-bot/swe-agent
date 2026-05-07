# Performance Review Checklist

This document provides guidelines for reviewing code performance during code reviews.

## Database Performance

### Query Optimization
- [ ] **N+1 Queries**: Are there loops that execute individual queries?
  - Use batch queries or joins instead
  - Example: `SELECT * FROM profiles WHERE user_id IN (...)` instead of individual queries

- [ ] **SELECT * Usage**: Are SELECT * queries avoided?
  - Only select needed columns
  - Reduces data transfer and parsing overhead

- [ ] **Query Efficiency**: Are queries optimized?
  - Use EXPLAIN/ANALYZE to check query plans
  - Ensure appropriate indexes are used
  - Avoid subqueries when joins are more efficient

- [ ] **Unnecessary Queries**: Are there redundant database calls?
  - Cache frequently accessed data
  - Combine multiple queries when possible

### Indexing
- [ ] Are appropriate indexes in place for:
  - WHERE clause columns
  - JOIN conditions
  - ORDER BY columns
  - Foreign key columns

- [ ] Are indexes not overused?
  - Too many indexes slow down writes
  - Remove unused indexes

### Connection Management
- [ ] Is connection pooling used?
- [ ] Are connections properly closed/returned to pool?
- [ ] Is the pool size configured appropriately?
- [ ] Are long-running transactions avoided?

### Data Loading Strategies
- [ ] **Pagination**: Is pagination used for large result sets?
- [ ] **Lazy Loading**: Is lazy loading used appropriately?
- [ ] **Eager Loading**: Are related entities loaded efficiently?
- [ ] **Batch Operations**: Are bulk inserts/updates used for multiple records?

## Async & Concurrency

### Async/Await Patterns
- [ ] Are I/O operations using async/await?
- [ ] Is async propagated correctly (no blocking in async context)?
- [ ] Are CPU-bound tasks offloaded from async context?
- [ ] Is proper error handling in async code?

### Concurrency Issues
- [ ] Are race conditions prevented?
- [ ] Is proper locking used for shared resources?
- [ ] Are deadlocks avoided?
- [ ] Is thread safety ensured where needed?

### Parallel Processing
- [ ] Should independent operations run in parallel?
- [ ] Are task limits/throttling configured?
- [ ] Is proper cleanup of async resources?

## Caching

### Caching Strategy
- [ ] Is caching used for frequently accessed data?
- [ ] Are cache keys well-designed and unique?
- [ ] Is cache invalidation strategy clear?
- [ ] Are cache expiration times appropriate?
- [ ] Is cache warming needed for critical data?

### Cache Levels
- [ ] **Application Cache**: In-memory caching for hot data
- [ ] **Distributed Cache**: Redis/Memcached for scalability
- [ ] **CDN**: Static assets served from CDN
- [ ] **HTTP Cache**: Proper cache headers set

### Cache Pitfalls
- [ ] Is stale data acceptable or handled?
- [ ] Is cache stampede prevented?
- [ ] Is cache size bounded to prevent memory issues?

## Algorithm & Data Structure Efficiency

### Time Complexity
- [ ] **O(n²) or worse**: Are nested loops over large datasets avoided?
  - Consider hash maps for O(1) lookups instead of linear search
  - Use sets for membership tests

- [ ] **Sorting**: Is sorting necessary? Is the right algorithm used?
  - Built-in sort is usually optimal (O(n log n))
  - Consider if partial sort is sufficient

- [ ] **Search**: Are efficient search structures used?
  - Binary search for sorted data: O(log n)
  - Hash maps for key-value lookups: O(1)
  - Trees for range queries

### Space Complexity
- [ ] Is memory usage reasonable?
- [ ] Are large objects created unnecessarily?
- [ ] Is data copied when references could be used?
- [ ] Are generators/iterators used for large datasets?

### Data Structure Choice
- [ ] **Lists**: Good for ordered access, poor for search
- [ ] **Sets**: Good for uniqueness and membership tests
- [ ] **Dictionaries**: Good for key-value lookups
- [ ] **Queues**: Good for FIFO operations
- [ ] **Heaps**: Good for priority operations

## Memory Management

### Memory Leaks
- [ ] Are resources properly cleaned up?
  - Database connections closed
  - File handles closed
  - Event listeners removed
  - Timers/intervals cleared

- [ ] Are circular references avoided (in languages with reference counting)?
- [ ] Are large objects released when no longer needed?
- [ ] Is there unbounded growth in caches or collections?

### Memory Optimization
- [ ] Are large files streamed instead of loaded entirely?
- [ ] Is pagination used for large datasets?
- [ ] Are objects pooled and reused if appropriate?
- [ ] Is lazy initialization used for expensive objects?

## Network Performance

### API Efficiency
- [ ] **Request Batching**: Are multiple requests combined?
- [ ] **Response Compression**: Is gzip/brotli enabled?
- [ ] **GraphQL**: Are over-fetching and under-fetching minimized?
- [ ] **Payload Size**: Is unnecessary data excluded from responses?

### External Service Calls
- [ ] Are timeouts configured for external calls?
- [ ] Is retry logic with exponential backoff implemented?
- [ ] Are failures handled gracefully (circuit breaker pattern)?
- [ ] Are external calls made in parallel when possible?

### HTTP Optimization
- [ ] Are HTTP/2 or HTTP/3 used if available?
- [ ] Is connection reuse enabled (Keep-Alive)?
- [ ] Are static resources cached with appropriate headers?
- [ ] Is CDN used for static assets?

## File I/O Performance

### File Operations
- [ ] Are large files streamed instead of read entirely?
- [ ] Is buffered I/O used?
- [ ] Are file operations async in async context?
- [ ] Are temporary files cleaned up?

### File System
- [ ] Is there excessive file system traversal?
- [ ] Are file stats cached when appropriate?
- [ ] Is batch reading/writing used for multiple files?

## Front-End Performance (if applicable)

### Rendering Performance
- [ ] Is unnecessary re-rendering prevented?
- [ ] Are expensive calculations memoized?
- [ ] Is virtual scrolling used for long lists?
- [ ] Are images lazy-loaded?
- [ ] Is code splitting used?

### Bundle Size
- [ ] Are unused dependencies removed?
- [ ] Is tree-shaking configured?
- [ ] Are large libraries imported selectively?
- [ ] Is bundle size monitored?

## Language-Specific Optimizations

### Python
- [ ] **List Comprehensions**: Used instead of loops where appropriate
- [ ] **Generators**: Used for large sequences to save memory
- [ ] **Built-in Functions**: Leveraged (map, filter, sum, etc.)
- [ ] **String Concatenation**: Join used instead of += in loops
- [ ] **Local Variables**: Lookups are faster than global/attribute lookups

```python
# ❌ Slow
result = ""
for item in items:
    result += str(item)

# ✅ Fast
result = "".join(str(item) for item in items)
```

### JavaScript/Node.js
- [ ] **Array Methods**: map/filter/reduce used appropriately
- [ ] **Debouncing/Throttling**: Used for frequent events
- [ ] **Lazy Loading**: Components/modules loaded on demand
- [ ] **Web Workers**: Used for CPU-intensive tasks

### Go
- [ ] **Goroutines**: Used for concurrent operations
- [ ] **Buffered Channels**: Used to prevent blocking
- [ ] **sync.Pool**: Used for object reuse
- [ ] **String Builder**: Used instead of string concatenation

### Java
- [ ] **StringBuilder**: Used for string concatenation in loops
- [ ] **Stream API**: Used appropriately (not always faster)
- [ ] **Object Pooling**: Used for expensive objects
- [ ] **Primitive Types**: Used instead of boxed types when possible

## Common Performance Anti-Patterns

### Database Anti-Patterns
```python
# ❌ N+1 Query Problem
users = User.query.all()
for user in users:
    profile = Profile.query.filter_by(user_id=user.id).first()  # N queries!

# ✅ Eager Loading
users = User.query.options(joinedload(User.profile)).all()
```

### Inefficient Loops
```python
# ❌ O(n²) lookup
for item in items:
    if item.id in [x.id for x in other_items]:  # Creates list every iteration!
        process(item)

# ✅ O(n) with set
other_ids = {x.id for x in other_items}
for item in items:
    if item.id in other_ids:  # O(1) lookup
        process(item)
```

### Unnecessary Data Loading
```python
# ❌ Loading entire table
all_users = User.query.all()
count = len(all_users)

# ✅ Count query
count = User.query.count()
```

### Memory Waste
```python
# ❌ Loading large file into memory
with open('huge_file.txt', 'r') as f:
    lines = f.readlines()  # Loads entire file!
    for line in lines:
        process(line)

# ✅ Streaming
with open('huge_file.txt', 'r') as f:
    for line in f:  # Reads line by line
        process(line)
```

## Performance Testing

### What to Test
- [ ] Load testing: How does it perform under expected load?
- [ ] Stress testing: Where does it break under high load?
- [ ] Spike testing: How does it handle sudden traffic spikes?
- [ ] Endurance testing: Are there memory leaks over time?

### Performance Metrics
- [ ] **Response Time**: Average, median, 95th/99th percentile
- [ ] **Throughput**: Requests per second
- [ ] **Error Rate**: Errors under load
- [ ] **Resource Usage**: CPU, memory, disk, network

### Profiling
- [ ] Have performance-critical sections been profiled?
- [ ] Are profiling results analyzed for bottlenecks?
- [ ] Is performance regression testing in place?

## Performance Budgets

### Response Time Targets
- [ ] API endpoints: < 200ms for simple queries
- [ ] Database queries: < 100ms for indexed lookups
- [ ] Page load: < 3s (< 1s for critical rendering)
- [ ] Background jobs: Appropriate timeout based on job type

### Resource Budgets
- [ ] Memory: Within allocated limits per service
- [ ] CPU: Sustained usage < 70% under normal load
- [ ] Disk I/O: Not saturating disk bandwidth
- [ ] Network: Efficient use of bandwidth

## Quick Performance Checklist

🏃 **Quick Wins to Look For:**
- [ ] N+1 database queries
- [ ] Missing database indexes
- [ ] Synchronous I/O in async code
- [ ] Large data loaded but only few fields used
- [ ] Nested loops over large datasets
- [ ] Repeated computation of same values
- [ ] No caching of frequently accessed data
- [ ] Large files loaded entirely into memory
- [ ] Inefficient string concatenation in loops
- [ ] Missing pagination for large result sets

## Red Flags

🚩 **Immediate Performance Concerns:**
- Nested database queries in loops (N+1)
- O(n²) or worse algorithm complexity on unbounded data
- Blocking I/O in async/event-loop contexts
- Loading entire large files into memory
- No timeout on external service calls
- Missing indexes on frequently queried columns
- Unbounded cache growth
- Memory leaks (resources not cleaned up)
- Excessive API calls that could be batched

## Tools & Profiling

### Recommended Tools
- **Database**: EXPLAIN, database slow query log
- **Python**: cProfile, line_profiler, memory_profiler
- **Node.js**: clinic.js, 0x, Chrome DevTools
- **Go**: pprof, trace
- **Java**: JProfiler, YourKit, VisualVM
- **General**: Application Performance Monitoring (APM) tools

## Resources

- [Performance Best Practices by Language]
- [Database Query Optimization Guides]
- [Async/Await Patterns]
- [Caching Strategies]
