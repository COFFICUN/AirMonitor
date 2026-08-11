# Frontend User Redesign Accessibility Review

Date: 2026-08-11

## Scope

The review covers the public routes, participant shell, overview, measurement
workflow, session history, bounded data table and charts, session-point map,
settings in light and dark themes, future-login explanation, cancellation
dialog, and the original Айри artwork.

## Standards and source decisions

- Modal focus behavior follows the WAI-ARIA Authoring Practices dialog pattern:
  focus enters the dialog, Tab and Shift+Tab remain contained, Escape closes,
  and focus returns to the invoking button.
  <https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/>
- Every full page provides a visible-on-focus skip link to its main landmark,
  consistent with WCAG technique H69.
  <https://www.w3.org/WAI/WCAG22/Techniques/html/H69>
- Responsive structure uses semantic landmarks and labelled navigation rather
  than relying on viewport metadata or disabling browser zoom.
  <https://www.w3.org/WAI/WCAG22/Techniques/html/H102>

## Automated evidence

`npx playwright test e2e/accessibility.spec.ts` passed 4 of 4 tests with zero
serious or critical axe findings across every public and participant route in
explicit light and dark themes, plus the keyboard-operated dialog state:

1. `/`, `/about`, `/participate`, `/methodology`, and `/login` in light theme;
2. the same five public routes in dark theme;
3. `/app`, device, measurement, data, map, and settings in both themes;
4. active-session cancellation dialog.

The dark-theme route matrix also repeats at 390×844 with axe and explicit
horizontal-overflow assertions.

The new dark-public regression reproduced the reported defect with contrast as
low as 1.02:1 for headings, 1.5:1 for navigation, and 1.69:1 for the primary
button. Public surfaces now follow semantic theme tokens, and primary controls
use dedicated foreground/background tokens. No axe rule was disabled or
excluded.

## Keyboard and focus review

- Public and app navigation use links; actions use buttons.
- The public mobile menu exposes `aria-expanded`, has a stable controlled
  region, closes on link activation, and closes with Escape.
- The cancellation confirmation uses `role="alertdialog"`, an accessible name
  and description, safe initial focus on “Вернуться”, two-way Tab containment,
  Escape close, body scroll lock, and trigger-focus restoration.
- App and public skip links target focusable main elements.
- Selected sessions use `aria-pressed`; status messages and safe errors use
  appropriate status or alert semantics.
- Focus rings remain visible and no global outline suppression is present.

## Non-colour and alternative presentation

- Status badges include text and a marker; colour is never the only meaning.
- Concentration states have textual labels and are never presented as AQI.
- Every chart has a textual min/max/count summary and the exact values remain in
  a horizontally contained semantic table.
- Map state is duplicated in session and point details. Disabling tiles or a
  map failure leaves lists, chart, table, coordinates, and workflow controls.
- Missing metric values render as an em dash and are not silently converted to
  zero.

## Motion and responsive review

- `prefers-reduced-motion` and the local reduced-motion preference disable Айри
  movement and interface transitions.
- The participant layout passed explicit no-horizontal-overflow checks at
  360×800, 390×844, 768×1024, 1280×800, and 1440×900.
- Desktop uses the complete sidebar; widths through 900 px use the five-action
  bottom navigation. Device and settings remain reachable through labelled
  header links.
- Tables scroll inside their own container and do not expand the page.

## Manual visual evidence

Twenty deterministic screenshots were generated and visually inspected:

- [landing desktop](frontend-user-redesign-screenshots/01-landing-desktop.png)
- [about](frontend-user-redesign-screenshots/02-about.png)
- [participation](frontend-user-redesign-screenshots/03-participate.png)
- [methodology](frontend-user-redesign-screenshots/04-methodology.png)
- [future login](frontend-user-redesign-screenshots/05-login.png)
- [device](frontend-user-redesign-screenshots/06-device.png)
- [overview](frontend-user-redesign-screenshots/07-overview.png)
- [active measurement](frontend-user-redesign-screenshots/08-active-measurement.png)
- [sessions](frontend-user-redesign-screenshots/09-sessions.png)
- [data](frontend-user-redesign-screenshots/10-data.png)
- [session-point map](frontend-user-redesign-screenshots/11-map.png)
- [settings](frontend-user-redesign-screenshots/12-settings.png)
- [landing mobile](frontend-user-redesign-screenshots/13-landing-mobile.png)
- [overview mobile](frontend-user-redesign-screenshots/14-overview-mobile.png)
- [settings dark theme](frontend-user-redesign-screenshots/15-settings-dark.png)
- [landing dark theme](frontend-user-redesign-screenshots/16-landing-dark.png)
- [about dark theme](frontend-user-redesign-screenshots/17-about-dark.png)
- [participation dark theme](frontend-user-redesign-screenshots/18-participate-dark.png)
- [methodology dark theme](frontend-user-redesign-screenshots/19-methodology-dark.png)
- [future login dark theme](frontend-user-redesign-screenshots/20-login-dark.png)

The review corrected test-tile readability, live-freshness spacing, active
timer fixture realism, mobile lazy-route capture, public dark-theme contrast,
and site-wide Cyrillic typography before accepting the set.

## Residual limitations

- Axe and this manual pass do not replace testing with multiple screen readers
  and users of assistive technology.
- Leaflet keyboard behavior is supplementary; session facts never depend on
  the map alone.
- The five-item mobile bottom navigation prioritizes core workflow routes.
  “Моё устройство” and “Настройки” remain available from the header rather
  than occupying two additional narrow tabs.

No Critical or Required accessibility finding remains in the reviewed code.
