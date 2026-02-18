# KodBro (Ionic + Tailwind)

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
cd KodBro-app
npm install
npm start
```

Then open `http://localhost:4200`. The app starts on the splash screen, then goes to the welcome page.

## Build (web)

```bash
npm run build
```

Output is in the `www` folder.

## Build for Android

**Prerequisites:** Java (JDK 17+), Android Studio, Android SDK.

1. Build and sync: `npm run build && npm run sync`
2. Open in Android Studio: `npx cap open android`
3. In Android Studio: Build → Build Bundle(s) / APK(s) → Build APK(s), or run on a device/emulator.

Or use the shortcut: `npm run build:android` (builds, syncs, then opens Android Studio).

## Build for iOS

**Prerequisites:** macOS, Xcode, CocoaPods (`brew install cocoapods`).

1. Add the iOS platform (one-time, if not already added): `npx cap add ios`
2. Build and sync: `npm run build && npm run sync`
3. Open in Xcode: `npx cap open ios`
4. In Xcode: Select a simulator or device, then Product → Run.

Or use the shortcut: `npm run build:ios` (builds, syncs, then opens Xcode).

**Note:** The project uses Capacitor 7 (Node 20–compatible). Android is already added; add iOS after installing CocoaPods if needed.
