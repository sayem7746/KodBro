# Live Activity & Dynamic Island Setup

KodBro uses iOS Live Activities to show agent build status on the **Lock Screen** and **Dynamic Island** (iPhone 14 Pro+).

## Xcode Setup (Required)

The Widget Extension must be added manually in Xcode:

### 1. Add Widget Extension

1. Open `ios/App/App.xcworkspace` in Xcode
2. **File → New → Target…**
3. Select **Widget Extension**
4. Click **Next**
5. Name: `LiveActivityWidget`
6. **Check "Include Live Activity"**
7. Uncheck "Include Configuration App Intent"
8. Click **Finish**
9. If prompted "Activate scheme?", click **Activate**

### 2. Replace Widget Code

1. Delete the default `LiveActivityWidgetLiveActivity.swift` and `LiveActivityWidgetBundle.swift` that Xcode created
2. In the Project Navigator, **right-click** the `LiveActivityWidget` folder → **Add Files to "App"…**
3. Navigate to `ios/App/LiveActivityWidget/`
4. Select `GenericAttributes.swift` and `LiveActivityWidgetLiveActivity.swift`
5. **Ensure "Copy items if needed" is unchecked** (files stay in place)
6. **Target membership**: check **LiveActivityWidget** for both files
7. Create a new Swift file `LiveActivityWidgetBundle.swift` in the LiveActivityWidget target with:

```swift
import WidgetKit
import SwiftUI

@main
struct LiveActivityWidgetBundle: WidgetBundle {
    var body: some Widget {
        if #available(iOS 16.2, *) {
            LiveActivityWidgetLiveActivity()
        }
    }
}
```

### 3. Add Capabilities

1. Select the **App** target (main app)
2. **Signing & Capabilities** tab
3. Click **+ Capability**
4. Add **Push Notifications**
5. Add **Live Activities** (search for it)

### 4. Build & Run

1. Connect a **real iOS device** (Live Activities don't work in Simulator)
2. Select your device
3. Build and run (⌘R)

When you start building an app with the agent, the status will appear on the Lock Screen and in the Dynamic Island.
