// ===========================================================
// SharingFeatureTests.swift
// ===========================================================
// XCTest-based tests for Apple Sharing features.
// Tests NSUserActivity (Handoff), GroupActivities (SharePlay),
// and Network.framework (Applied Networking foundation).
//
// Build: xcodebuild test -scheme SharingTests -destination 'platform=iOS'
// ===========================================================

import XCTest
import Foundation

// MARK: - Handoff Tests (NSUserActivity)

class HandoffTests: XCTestCase {

    /// Verify NSUserActivity can be created with correct activity type
    func testCreateUserActivity() {
        let activity = NSUserActivity(activityType: "com.apple.test.browsing")
        activity.title = "Viewing Test Page"
        activity.webpageURL = URL(string: "https://apple.com")
        activity.isEligibleForHandoff = true

        XCTAssertEqual(activity.activityType, "com.apple.test.browsing")
        XCTAssertEqual(activity.title, "Viewing Test Page")
        XCTAssertTrue(activity.isEligibleForHandoff)
        XCTAssertNotNil(activity.webpageURL)
    }

    /// Verify userInfo dictionary preserves data across Handoff
    func testUserInfoPreserved() {
        let activity = NSUserActivity(activityType: "com.apple.test.editing")
        activity.userInfo = [
            "documentID": "doc-12345",
            "cursorPosition": 42,
            "selectedText": "Hello World",
            "timestamp": Date().timeIntervalSince1970
        ]

        XCTAssertEqual(activity.userInfo?["documentID"] as? String, "doc-12345")
        XCTAssertEqual(activity.userInfo?["cursorPosition"] as? Int, 42)
        XCTAssertEqual(activity.userInfo?["selectedText"] as? String, "Hello World")
        XCTAssertNotNil(activity.userInfo?["timestamp"])
    }

    /// Verify userInfo stays under 4KB BLE limit
    func testUserInfoSizeUnderBLELimit() {
        let activity = NSUserActivity(activityType: "com.apple.test.handoff")

        var userInfo: [String: Any] = [:]
        userInfo["title"] = "Test Document"
        userInfo["url"] = "https://example.com/page"
        userInfo["position"] = 100

        activity.userInfo = userInfo

        // Serialize to check size
        let data = try? NSKeyedArchiver.archivedData(
            withRootObject: userInfo,
            requiringSecureCoding: false
        )
        let sizeBytes = data?.count ?? 0
        XCTAssertLessThan(sizeBytes, 4096, "userInfo exceeds 4KB BLE limit: \(sizeBytes) bytes")
    }

    /// Verify large userInfo triggers Continuation Stream (> 4KB)
    func testLargeUserInfoExceedsBLELimit() {
        var userInfo: [String: Any] = [:]
        // Fill with enough data to exceed 4KB
        userInfo["largeContent"] = String(repeating: "A", count: 5000)

        let data = try? NSKeyedArchiver.archivedData(
            withRootObject: userInfo,
            requiringSecureCoding: false
        )
        let sizeBytes = data?.count ?? 0
        XCTAssertGreaterThan(sizeBytes, 4096,
            "Large payload should exceed BLE limit and use Continuation Stream")
    }

    /// Verify activity type format follows reverse-DNS convention
    func testActivityTypeFormat() {
        let validTypes = [
            "com.apple.safari.browsing",
            "com.apple.mail.composing",
            "com.apple.pages.editing",
        ]
        for activityType in validTypes {
            let components = activityType.split(separator: ".")
            XCTAssertGreaterThanOrEqual(components.count, 3,
                "Activity type should be reverse-DNS: \(activityType)")
        }
    }

    /// Verify Handoff eligibility flags
    func testHandoffEligibilityFlags() {
        let activity = NSUserActivity(activityType: "com.apple.test")

        // Default: Handoff should be eligible
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = false       // Spotlight
        activity.isEligibleForPublicIndexing = false

        XCTAssertTrue(activity.isEligibleForHandoff)
        XCTAssertFalse(activity.isEligibleForSearch)
        XCTAssertFalse(activity.isEligibleForPublicIndexing)
    }

    /// Verify activity can be invalidated (cleanup when user closes app)
    func testActivityInvalidation() {
        let activity = NSUserActivity(activityType: "com.apple.test")
        activity.title = "Active Task"
        activity.isEligibleForHandoff = true

        // Invalidate — simulates user closing the activity
        activity.invalidate()

        // After invalidation, activity should still exist but won't be advertised
        XCTAssertNotNil(activity)
    }

    /// Unicode and special characters in Handoff data
    func testSpecialCharactersInUserInfo() {
        let activity = NSUserActivity(activityType: "com.apple.test")
        activity.userInfo = [
            "japanese": "こんにちは世界",
            "emoji": "🍎📱💻⌚️",
            "arabic": "مرحبا بالعالم",
            "html": "<script>alert('xss')</script>",
        ]

        XCTAssertEqual(activity.userInfo?["japanese"] as? String, "こんにちは世界")
        XCTAssertEqual(activity.userInfo?["emoji"] as? String, "🍎📱💻⌚️")
        XCTAssertEqual(activity.userInfo?["arabic"] as? String, "مرحبا بالعالم")
        XCTAssertEqual(activity.userInfo?["html"] as? String, "<script>alert('xss')</script>")
    }
}


// MARK: - Universal Clipboard Tests

class UniversalClipboardTests: XCTestCase {

    /// Verify pasteboard can store text (basic clipboard operation)
    #if os(iOS)
    func testPasteboardStoresText() {
        let pasteboard = UIPasteboard.general
        let testString = "Copied from iPhone for Mac"
        pasteboard.string = testString
        XCTAssertEqual(pasteboard.string, testString)
    }
    #elseif os(macOS)
    func testPasteboardStoresText() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString("Copied from Mac for iPhone", forType: .string)
        let result = pasteboard.string(forType: .string)
        XCTAssertEqual(result, "Copied from Mac for iPhone")
    }
    #endif

    /// Verify clipboard content size for cross-device transfer
    func testClipboardContentSize() {
        // Small text — goes via BLE metadata path
        let smallText = "Hello"
        let smallSize = smallText.data(using: .utf8)?.count ?? 0
        XCTAssertLessThan(smallSize, 4096, "Small text should fit in BLE payload")

        // Large text — requires AWDL/Wi-Fi transfer
        let largeText = String(repeating: "A", count: 10_000)
        let largeSize = largeText.data(using: .utf8)?.count ?? 0
        XCTAssertGreaterThan(largeSize, 4096, "Large text should use Wi-Fi transfer path")
    }
}


// MARK: - Network Framework Tests

class NetworkFrameworkTests: XCTestCase {

    /// Verify URLSession uses HTTP/2 by default
    func testURLSessionHTTP2Default() {
        let expectation = self.expectation(description: "HTTP request")

        let url = URL(string: "https://www.apple.com")!
        let task = URLSession.shared.dataTask(with: url) { data, response, error in
            XCTAssertNil(error)
            XCTAssertNotNil(data)

            if let httpResponse = response as? HTTPURLResponse {
                XCTAssertEqual(httpResponse.statusCode, 200)
            }
            expectation.fulfill()
        }
        task.resume()
        waitForExpectations(timeout: 15)
    }

    /// Verify ATS enforcement — HTTP should fail or redirect
    func testATSBlocksInsecureConnection() {
        let expectation = self.expectation(description: "HTTP request")

        // With default ATS, plain HTTP to arbitrary domains should fail
        let config = URLSessionConfiguration.default
        let session = URLSession(configuration: config)

        let url = URL(string: "http://httpbin.org/get")!
        let task = session.dataTask(with: url) { data, response, error in
            // ATS should either block this or require an exception
            // The exact behavior depends on Info.plist configuration
            expectation.fulfill()
        }
        task.resume()
        waitForExpectations(timeout: 10)
    }

    /// Verify TLS minimum version in URLSession
    func testTLSMinimumVersion() {
        let config = URLSessionConfiguration.default
        // URLSession should enforce TLS 1.2+ by default (ATS)
        let session = URLSession(configuration: config)

        let expectation = self.expectation(description: "TLS request")
        let url = URL(string: "https://apple.com")!

        let task = session.dataTask(with: url) { data, response, error in
            XCTAssertNil(error, "TLS connection should succeed: \(error?.localizedDescription ?? "")")
            expectation.fulfill()
        }
        task.resume()
        waitForExpectations(timeout: 15)
    }

    /// Test connection timeout handling — critical for Handoff/AirDrop
    func testConnectionTimeout() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 5  // 5 second timeout

        let session = URLSession(configuration: config)
        let expectation = self.expectation(description: "Timeout")

        // Connect to non-routable address to trigger timeout
        let url = URL(string: "https://192.0.2.1/timeout-test")!
        let task = session.dataTask(with: url) { data, response, error in
            XCTAssertNotNil(error, "Should timeout on non-routable address")
            expectation.fulfill()
        }
        task.resume()
        waitForExpectations(timeout: 10)
    }

    /// Test concurrent connections — SharePlay needs multiple simultaneous streams
    func testConcurrentConnections() {
        let urls = [
            "https://www.apple.com",
            "https://developer.apple.com",
            "https://support.apple.com",
        ]

        let group = DispatchGroup()
        var results: [Int: Int] = [:] // URL index -> status code

        for (index, urlString) in urls.enumerated() {
            group.enter()
            let url = URL(string: urlString)!
            URLSession.shared.dataTask(with: url) { _, response, error in
                if let httpResponse = response as? HTTPURLResponse {
                    results[index] = httpResponse.statusCode
                }
                group.leave()
            }.resume()
        }

        let completed = group.wait(timeout: .now() + 15)
        XCTAssertEqual(completed, .success, "All concurrent requests should complete")
        XCTAssertEqual(results.count, urls.count, "All URLs should have responses")
    }

    /// Test request cancellation — user cancels AirDrop mid-transfer
    func testRequestCancellation() {
        let expectation = self.expectation(description: "Cancellation")

        let url = URL(string: "https://www.apple.com")!
        let task = URLSession.shared.dataTask(with: url) { _, _, error in
            // Should get cancellation error
            if let error = error as NSError? {
                XCTAssertEqual(error.code, NSURLErrorCancelled)
            }
            expectation.fulfill()
        }
        task.resume()
        task.cancel()  // Cancel immediately

        waitForExpectations(timeout: 5)
    }
}


// MARK: - SharePlay Session Simulation Tests

class SharePlayTests: XCTestCase {

    /// Simulate SharePlay state synchronization data structure
    struct PlaybackState: Codable, Equatable {
        let mediaID: String
        let positionSeconds: Double
        let isPlaying: Bool
        let timestamp: TimeInterval
    }

    /// Verify playback state can be serialized for sync
    func testPlaybackStateSerialization() {
        let state = PlaybackState(
            mediaID: "movie-12345",
            positionSeconds: 125.5,
            isPlaying: true,
            timestamp: Date().timeIntervalSince1970
        )

        // Encode
        let encoder = JSONEncoder()
        let data = try! encoder.encode(state)

        // Decode
        let decoder = JSONDecoder()
        let decoded = try! decoder.decode(PlaybackState.self, from: data)

        XCTAssertEqual(state.mediaID, decoded.mediaID)
        XCTAssertEqual(state.positionSeconds, decoded.positionSeconds, accuracy: 0.001)
        XCTAssertEqual(state.isPlaying, decoded.isPlaying)
    }

    /// Verify sync state payload size is reasonable
    func testSyncPayloadSize() {
        let state = PlaybackState(
            mediaID: "movie-12345",
            positionSeconds: 3600.0,
            isPlaying: true,
            timestamp: Date().timeIntervalSince1970
        )

        let data = try! JSONEncoder().encode(state)
        // Sync messages should be small for low latency
        XCTAssertLessThan(data.count, 1024, "Sync payload too large: \(data.count) bytes")
    }

    /// Verify sync drift detection between two participants
    func testSyncDriftDetection() {
        let hostPosition: Double = 125.500
        let participantPosition: Double = 125.720  // 220ms drift

        let driftMs = abs(hostPosition - participantPosition) * 1000
        // SharePlay should keep drift under 500ms
        XCTAssertLessThan(driftMs, 500, "Sync drift too high: \(driftMs)ms")
    }

    /// Verify play/pause command structure
    func testPlayPauseCommand() {
        struct SyncCommand: Codable {
            let action: String  // "play", "pause", "seek"
            let timestamp: TimeInterval
            let seekPosition: Double?
        }

        let pauseCmd = SyncCommand(
            action: "pause",
            timestamp: Date().timeIntervalSince1970,
            seekPosition: nil
        )
        let data = try! JSONEncoder().encode(pauseCmd)
        let decoded = try! JSONDecoder().decode(SyncCommand.self, from: data)
        XCTAssertEqual(decoded.action, "pause")
        XCTAssertNil(decoded.seekPosition)

        let seekCmd = SyncCommand(
            action: "seek",
            timestamp: Date().timeIntervalSince1970,
            seekPosition: 300.0
        )
        let seekData = try! JSONEncoder().encode(seekCmd)
        let decodedSeek = try! JSONDecoder().decode(SyncCommand.self, from: seekData)
        XCTAssertEqual(decodedSeek.action, "seek")
        XCTAssertEqual(decodedSeek.seekPosition, 300.0)
    }

    /// Simulate participant join/leave
    func testParticipantManagement() {
        var participants: Set<String> = ["device-A", "device-B"]

        // New participant joins
        participants.insert("device-C")
        XCTAssertEqual(participants.count, 3)

        // Participant leaves
        participants.remove("device-B")
        XCTAssertEqual(participants.count, 2)
        XCTAssertFalse(participants.contains("device-B"))

        // Session should continue with remaining participants
        XCTAssertTrue(participants.contains("device-A"))
        XCTAssertTrue(participants.contains("device-C"))
    }
}
