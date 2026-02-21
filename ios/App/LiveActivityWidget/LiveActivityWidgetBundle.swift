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
