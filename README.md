# Replit App (Ionic + Tailwind)

Ionic Angular app with splash screen, welcome page, and auth page, styled with Tailwind CSS and a custom color palette.

## Color palette

| Name   | Hex       | Tailwind class |
|--------|-----------|----------------|
| Maroon | `#7F2220` | `maroon`       |
| Red    | `#D13E3B` | `red`          |
| Cream  | `#F8F2E4` | `cream`        |
| Navy   | `#22374F` | `navy`         |
| Steel  | `#85A9CB` | `steel`        |

## Pages

- **Splash** (`/` or `/splash`) – Full-screen splash with palette strip; auto-navigates to Welcome after 2.5s.
- **Welcome** (`/welcome`) – Welcome screen with “Sign in” and “Create account” buttons linking to Auth.
- **Auth** (`/auth`) – Sign-in form (email/password) with back button to Welcome.

## Run locally

```bash
cd replit-app
npm install
npm start
```

Then open `http://localhost:4200`. The app starts on the splash screen, then goes to the welcome page.

## Build

```bash
npm run build
```

Output is in the `www` folder.
