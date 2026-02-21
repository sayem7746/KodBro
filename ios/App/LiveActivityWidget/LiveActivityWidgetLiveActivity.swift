import ActivityKit
import WidgetKit
import SwiftUI

@available(iOS 16.2, *)
struct LiveActivityWidgetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: GenericAttributes.self) { context in
            // Lock Screen UI
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("KodBro")
                        .font(.headline)
                        .fontWeight(.semibold)
                    Spacer()
                    Image(systemName: "hammer.fill")
                        .font(.caption)
                }
                Text(context.state.values["status"] ?? "Building…")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Text(context.state.values["message"] ?? "")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
            .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 6) {
                        Image(systemName: "hammer.fill")
                            .font(.title3)
                        Text(context.state.values["title"] ?? "KodBro")
                            .font(.headline)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.values["status"] ?? "Building…")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text(context.state.values["message"] ?? "")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
            } compactLeading: {
                Image(systemName: "hammer.fill")
            } compactTrailing: {
                Text(context.state.values["status"] ?? "…")
                    .font(.caption2)
                    .lineLimit(1)
            } minimal: {
                Image(systemName: "hammer.fill")
            }
        }
    }
}
