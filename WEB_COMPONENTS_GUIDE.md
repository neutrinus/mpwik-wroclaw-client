# MPWiK Wrocław Web Components & Shadow DOM Guide

This document describes the DOM structure and Shadow DOM components of the MPWiK Wrocław eBOK login page. This information is essential for browser automation and understanding the website architecture.

**Last Updated:** 2025-11-12  
**Website:** https://ebok.mpwik.wroc.pl/

## Overview

The MPWiK eBOK website uses Web Components with Shadow DOM encapsulation. This means:

- **Standard Selenium selectors cannot access elements inside shadow roots**
- **JavaScript must be used** to traverse the shadow DOM tree
- **Some components have nested shadow roots** requiring multiple levels of traversal
- **Not all custom elements use shadow DOM** - implementation is inconsistent

## Cookie Consent Overlay

### Structure

```
k-cookie-consent (web component)
└─ [shadowRoot]
   └─ div.overlay
      └─ div.main
         └─ div.flex-col
            └─ div.flex-row
               └─ k-button[raised][label="Akceptuj"]
                  └─ [shadowRoot]
                     └─ button#button.mdc-button.mdc-button--raised
```

### JavaScript Access

```javascript
// Get the cookie consent component
const cookieConsent = document.querySelector('k-cookie-consent');
const cookieRoot = cookieConsent.shadowRoot;

// Get the overlay div
const overlay = cookieRoot.querySelector('div.overlay');

// Get the k-button component
const kButton = cookieRoot.querySelector('k-button[raised]');
const buttonRoot = kButton.shadowRoot;

// Get the actual button element
const actualButton = buttonRoot.querySelector('button#button');
actualButton.click();
```

### Visibility Check

```javascript
// Check if overlay is visible
const overlay = document.querySelector('k-cookie-consent')
  .shadowRoot.querySelector('div.overlay');
const isHidden = overlay.hasAttribute('hidden');
const isVisible = !isHidden && 
                  overlay.style.display !== 'none' &&
                  getComputedStyle(overlay).display !== 'none';
```

### Overlay States

**Before Dismissal:**
```html
<k-cookie-consent>
  #shadow-root
    <div class="overlay"> <!-- VISIBLE -->
      ...
    </div>
</k-cookie-consent>
<body class="noscroll">
```

**After Dismissal:**
```html
<k-cookie-consent>
  #shadow-root
    <div class="overlay" hidden=""> <!-- HIDDEN -->
      ...
    </div>
</k-cookie-consent>
<body class="">
```

## Login Form Fields

The login form uses custom web components with nested shadow roots.

### Login Field Structure

```
k-login-field#login (web component)
├─ [attributes]
│  ├─ id="login"
│  ├─ name="login"
│  ├─ label="Login"
│  ├─ placeholder="Adres e-mail lub numer klienta"
│  ├─ required
│  ├─ autofocus
│  └─ fullwidth
└─ [shadowRoot]
   └─ label.mdc-text-field.mdc-text-field--filled
      ├─ span.mdc-floating-label#login-label
      └─ input.mdc-text-field__input
         ├─ type="text"
         ├─ aria-labelledby="login-label"
         ├─ placeholder="Adres e-mail lub numer klienta"
         └─ required
```

**Note:** The `k-login-field` implementation is inconsistent - in some versions it may render directly into the DOM without shadow encapsulation. Always check for `shadowRoot` before accessing.

### Password Field Structure (Nested Shadow Roots)

```
k-current-password#password (web component)
├─ [attributes]
│  ├─ id="password"
│  ├─ name="password"
│  └─ required
└─ [shadowRoot] (Level 1)
   └─ div.container
      └─ mwc-textfield.password-field
         ├─ [attributes]
         │  ├─ name="password"
         │  ├─ label="Hasło"
         │  ├─ required
         │  ├─ type="password"
         │  ├─ minlength="3"
         │  ├─ maxlength="120"
         │  └─ validationmessage="Wprowadź poprawne hasło"
         └─ [shadowRoot] (Level 2)
            └─ label.mdc-text-field.mdc-text-field--filled
               └─ input.mdc-text-field__input
                  ├─ type="password"
                  ├─ aria-labelledby="label"
                  ├─ required
                  ├─ minlength="3"
                  ├─ maxlength="120"
                  └─ name="password"
```

### JavaScript Access Patterns

#### Login Field

```javascript
// Get the login field component
const loginField = document.querySelector('k-login-field#login');
const loginRoot = loginField.shadowRoot;

// Get the input element
const loginInput = loginRoot.querySelector('input.mdc-text-field__input');

// Set value and trigger events
loginInput.value = 'your-login';
loginInput.dispatchEvent(new Event('input', { bubbles: true }));
loginInput.dispatchEvent(new Event('change', { bubbles: true }));
```

#### Password Field

```javascript
// Get the password component
const passwordComponent = document.querySelector('k-current-password#password');
const passwordRoot = passwordComponent.shadowRoot;

// Get the mwc-textfield component (first level)
const mwcTextField = passwordRoot.querySelector('mwc-textfield');
const mwcRoot = mwcTextField.shadowRoot;

// Get the actual input element (second level)
const passwordInput = mwcRoot.querySelector('input.mdc-text-field__input');

// Set value and trigger events
passwordInput.value = 'your-password';
passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
passwordInput.dispatchEvent(new Event('change', { bubbles: true }));
```

### Form Validation States

The login field can have these CSS classes:
- `mdc-text-field--invalid` - when validation fails
- `mdc-text-field--label-floating` - when label is floating above input
- `mdc-ripple-upgraded` - Material Design ripple effect applied

Helper text example:
```html
<div class="mdc-text-field-helper-line">
    <div class="mdc-text-field-helper-text mdc-text-field-helper-text--validation-msg" 
         id="login-helper" 
         role="alert">
        Wprowadź login
    </div>
</div>
```

## Login Button

### Structure

```
k-button#login-button (web component)
├─ [attributes]
│  ├─ id="login-button"
│  ├─ raised
│  ├─ label="Zaloguj się"
│  └─ fullwidth
└─ [shadowRoot]
   └─ button#button.mdc-button.mdc-button--raised
      ├─ aria-label="Zaloguj się"
      └─ span.mdc-button__label
         └─ "Zaloguj się"
```

### JavaScript Access

```javascript
// Get the login button component
const loginButton = document.querySelector('k-button#login-button');
const buttonRoot = loginButton.shadowRoot;

// Get the actual button
const button = buttonRoot.querySelector('button#button');
button.click();
```

## Complete Page Structure

Here's the complete login page structure after dismissing the cookie overlay:

```html
<body>
  <!-- Cookie Consent (hidden after acceptance) -->
  <k-cookie-consent>
    #shadow-root
      <div class="overlay" hidden="">...</div>
  </k-cookie-consent>

  <!-- Header -->
  <header>
    <k-header-public>...</k-header-public>
  </header>

  <!-- Main Content -->
  <main id="outlet">
    <login-page>
      <div class="container py-2">
        <div class="login-page-content">
          <!-- Login Card -->
          <div class="card mb-4 rounded-3 shadow-sm">
            <div class="card-body">
              <form id="loginForm" action="/trust/" method="post">
                <!-- Login Field -->
                <k-login-field id="login" name="login">
                  #shadow-root
                    <input class="mdc-text-field__input" type="text">
                </k-login-field>

                <!-- Password Field -->
                <k-current-password id="password" name="password">
                  #shadow-root
                    <mwc-textfield class="password-field">
                      #shadow-root
                        <input class="mdc-text-field__input" type="password">
                    </mwc-textfield>
                </k-current-password>
              </form>
            </div>

            <!-- Login Button -->
            <div class="card-footer">
              <k-button id="login-button" raised="" label="Zaloguj się">
                #shadow-root
                  <button id="button" class="mdc-button mdc-button--raised">
              </k-button>
            </div>
          </div>
        </div>
      </div>
    </login-page>
  </main>

  <!-- Footer -->
  <footer>...</footer>

  <!-- reCAPTCHA Badge -->
  <div class="grecaptcha-badge">...</div>
</body>
```

## reCAPTCHA Integration

The site uses Google reCAPTCHA v3:
```html
<meta name="recaptcha.site.key" content="6Lf8vB8mAAAAALHS9a5UlXv-xuyTB8Vp_VFxSecZ">
```

The reCAPTCHA badge appears in the bottom-right corner and is mostly handled automatically by the browser.

## Selenium Integration Strategy

Since standard Selenium selectors cannot traverse shadow DOM, use JavaScript execution:

```python
# Example: Access login input
driver.execute_script("""
    const loginField = document.querySelector('k-login-field#login');
    const input = loginField.shadowRoot.querySelector('input');
    input.value = arguments[0];
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
""", login_value)

# Example: Access password input through nested shadow roots
driver.execute_script("""
    const passwordComp = document.querySelector('k-current-password#password');
    const textfield = passwordComp.shadowRoot.querySelector('mwc-textfield');
    const input = textfield.shadowRoot.querySelector('input');
    input.value = arguments[0];
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
""", password_value)
```

## Important Notes

### Shadow DOM Traversal
1. **Cannot use standard Selenium selectors** - Elements inside shadow roots are not accessible via CSS selectors or XPath
2. **Must use JavaScript** - Use `element.shadowRoot` to access shadow DOM content
3. **Nested shadow roots** - Some components (like password field) have multiple levels of shadow roots
4. **Check for null** - Always verify `shadowRoot` exists before accessing

### Event Dispatching
When setting input values via JavaScript, you **must** dispatch events to trigger validation:
```javascript
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
```

### Material Web Components (MWC)
The site uses Material Web Components which follow Material Design principles:
- `mdc-text-field` - Text input fields
- `mdc-button` - Buttons
- `mdc-floating-label` - Floating labels for inputs

### Timing Considerations
- Wait at least 2 seconds after page load for shadow DOM components to initialize
- Cookie overlay may take up to 10 seconds to appear
- Form validation happens on input/change events
- Wait for animations to complete before interacting with elements

### Key Observations
1. **Inconsistent Shadow DOM Usage** - Not all custom elements use shadow DOM (e.g., `k-login-field` implementation varies)
2. **Nested Shadow Roots** - Some components have nested shadow roots (e.g., `k-current-password` > `mwc-textfield`)
3. **Material Design Components** - The site uses Material Web Components (MWC) which have their own shadow roots
4. **Event Dispatch Required** - After setting values via JavaScript, dispatch `input` and `change` events
5. **Attribute-based Hiding** - Elements use `hidden=""` attribute for visibility control, not just CSS `display: none`

## Debugging Tips

### View Shadow DOM in Browser DevTools
1. Open Chrome/Edge DevTools (F12)
2. Go to Settings (⚙️) → Elements
3. Enable "Show user agent shadow DOM"
4. Shadow roots will appear as `#shadow-root` nodes in the Elements tree

### Test Selectors in Console
```javascript
// Test cookie overlay
document.querySelector('k-cookie-consent')
  .shadowRoot.querySelector('k-button')
  .shadowRoot.querySelector('button')

// Test login field
document.querySelector('k-login-field')
  .shadowRoot.querySelector('input')

// Test password field
document.querySelector('k-current-password')
  .shadowRoot.querySelector('mwc-textfield')
  .shadowRoot.querySelector('input')
```

### Check Element Visibility
```javascript
// Check if element is visible (not hidden by CSS or attributes)
function isVisible(element) {
  return element.offsetParent !== null && 
         !element.hasAttribute('hidden') &&
         window.getComputedStyle(element).display !== 'none';
}
```

### Test Shadow Root Existence
```javascript
// Test if element has shadow root
const element = document.querySelector('k-login-field');
console.log('Has shadow root:', element.shadowRoot !== null);

// Test nested shadow root access
const passwordComp = document.querySelector('k-current-password');
const textfield = passwordComp?.shadowRoot?.querySelector('mwc-textfield');
console.log('Found textfield:', textfield !== null);
```

## Troubleshooting

### Element Not Found
If you get "Cannot read property 'shadowRoot' of null":
- Wait for the element to load (use explicit waits)
- Check if the component actually uses shadow DOM
- Verify the selector is correct
- Ensure the page has fully loaded

### Values Not Saving
If values don't persist after setting:
- Ensure you dispatch `input` and `change` events
- Check for readonly/disabled attributes
- Verify the component has finished initializing
- Wait for validation to complete

### Click Not Working
If clicks don't register:
- Use JavaScript click: `element.click()`
- Ensure element is not covered by overlay
- Check if element is actually clickable (not disabled)
- Wait for any animations to complete
- Verify element is in viewport

### Shadow Root Access Fails
If shadow root access returns null:
- Component may not use shadow DOM in current version
- Element may not be fully initialized
- Check if site has been updated with different component structure
- Try accessing element directly without shadow root

## Version History

| Date       | Changes |
|------------|---------|
| 2025-11-12 | Consolidated DOM_STRUCTURE.md and SHADOW_DOM_STRUCTURE.md into comprehensive guide |
| 2025-11-11 | Initial documentation with Shadow DOM structure for cookie overlay and login form |

## Related Files

- `mpwik_browser_client.py` - Selenium browser automation implementation
- `mpwik_playwright_client.py` - Playwright browser automation implementation
- `README.md` - Complete documentation including usage examples
- `API.md` - REST API endpoint documentation

## References

- [Shadow DOM MDN Documentation](https://developer.mozilla.org/en-US/docs/Web/Web_Components/Using_shadow_DOM)
- [Material Web Components](https://github.com/material-components/material-web)
- [Selenium JavaScript Executor](https://www.selenium.dev/documentation/webdriver/interactions/javascript/)
- [Web Components](https://developer.mozilla.org/en-US/docs/Web/Web_Components)
