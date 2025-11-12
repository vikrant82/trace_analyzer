# Task Completion Checklist

When completing a task in the Trace_Analyser project, follow this checklist:

## 1. Code Verification

### Syntax Check
```bash
python3 -m py_compile <modified_file>.py
```

### Manual Testing
- If modified `analyze_trace.py`:
  ```bash
  python3 analyze_trace.py bug-archanata.json
  ```
- If modified `app.py` or templates:
  ```bash
  python3 app.py
  # Test in browser at http://localhost:5001
  ```

### API Testing (if applicable)
```bash
curl -X POST -F "file=@bug-archanata.json" http://localhost:5001/api/analyze
```

## 2. Code Quality

### Check for Common Issues
- [ ] All imports are present and correct
- [ ] Type hints are accurate
- [ ] Docstrings are updated for modified functions
- [ ] Private methods use underscore prefix
- [ ] Variable names follow snake_case convention
- [ ] Class names follow PascalCase convention
- [ ] No unused variables or imports

### Error Handling
- [ ] Try-except blocks where needed
- [ ] Meaningful error messages
- [ ] Resources cleaned up (temp files deleted)

## 3. Functionality Validation

### Core Features (if modified)
- [ ] Five-pass analysis pipeline works correctly
- [ ] Trace hierarchy displays properly
- [ ] Dynamic highlighting slider functions
- [ ] Expand/collapse works in UI
- [ ] Service mesh filtering works as expected
- [ ] Timing calculations are accurate
- [ ] Error tracking captures all errors

### Edge Cases
- [ ] Handles fragmented traces (missing parents)
- [ ] Handles large files (streaming parser)
- [ ] Handles missing HTTP methods (defaults properly)
- [ ] Handles multiple trace roots
- [ ] Handles empty traces

## 4. Documentation

### Code Comments
- [ ] Complex algorithms have explanatory comments
- [ ] Updated docstrings for modified functions
- [ ] Inline comments for non-obvious logic

### External Documentation
- [ ] Update README.md if feature changes
- [ ] Update QUICKSTART.md if usage changes
- [ ] Update architecture_summary.md if architecture changes

## 5. Version Control

### Git Workflow
```bash
# Check what changed
git status
git diff

# Stage changes
git add <modified_files>

# Commit with descriptive message
git commit -m "Brief description of changes

- Detailed point 1
- Detailed point 2"

# Push to remote (if applicable)
git push origin <branch>
```

## 6. Specific Feature Checks

### If Modified Trace Hierarchy
- [ ] Orphan adoption works correctly
- [ ] Self-time calculation is accurate
- [ ] Aggregation groups siblings properly
- [ ] Sidecar filtering removes duplicates
- [ ] Recalculation after filtering is correct

### If Modified Flask App
- [ ] All routes return proper status codes
- [ ] File validation works
- [ ] Temp files are cleaned up
- [ ] JSON responses have correct structure
- [ ] HTML templates render without errors

### If Modified Templates
- [ ] Jinja2 syntax is correct
- [ ] JavaScript functions work
- [ ] CSS classes are applied
- [ ] Responsive design maintained
- [ ] Accessibility considerations

## 7. Performance

### Check Performance (if relevant)
- [ ] No obvious performance regressions
- [ ] Large files still process efficiently
- [ ] Memory usage is reasonable
- [ ] Streaming parser still used for large files

## 8. Security

### Basic Security Checks
- [ ] File upload validation in place
- [ ] File size limits enforced
- [ ] No arbitrary code execution vulnerabilities
- [ ] Temp files have safe permissions

## 9. Final Review

### Before Marking Complete
- [ ] All tests pass
- [ ] Code follows project conventions
- [ ] No debugging code left behind (print statements, etc.)
- [ ] Comments are clear and helpful
- [ ] Documentation is updated
- [ ] Git commits are descriptive

## 10. Deployment Verification (Optional)

### Docker Build
```bash
docker build -t trace-analyzer .
docker run -p 5000:5000 trace-analyzer
# Test at http://localhost:5000
```

### Docker Compose
```bash
docker-compose up --build
# Test at http://localhost:5000
docker-compose down
```
