"""A small, curated seed dataset for first-run training.

This file ships in the repository so the AI service has *something* to fit on
when no ``merged_dataset.csv`` exists yet (offline deploys, fresh CI, demos).
The 4 classes are heavily unbalanced on purpose so the trained model behaves
predictably on any input it sees in the wild.

For production-quality training, ``merge_datasets.py`` downloads the larger
public corpora (Enron / phishing / SMS) and writes a fuller
``merged_dataset.csv`` -- that file takes precedence over this seed file.
"""

SEED_LABELS = ("normal", "notification", "spam", "scam")

# A small but hand-picked set of realistic email samples.  Each row is
# (label, subject, body) where body is short enough to keep this file
# readable but long enough to give TF-IDF some signal.
SEED_ROWS: list[tuple[str, str, str]] = [
    # ===========================
    # NORMAL (24 samples)
    # ===========================
    ("normal", "Lunch on Friday?", "Hey Sarah, are we still on for lunch on Friday? Let me know what time works for you."),
    ("normal", "Re: Project sync notes", "Hi team, attaching the meeting notes from yesterday's sync. Let me know if anything is missing."),
    ("normal", "Quarterly report draft", "Please find the quarterly report draft attached. Feedback is welcome by end of day Thursday."),
    ("normal", "Family weekend", "We're thinking of coming to visit next weekend. Would you be around Saturday afternoon?"),
    ("normal", "Re: doc review", "Thanks for the comments. I've rolled most of them in -- see the latest diff in the shared drive."),
    ("normal", "Quick question about the API", "Do you have a minute to chat about the rate limit on the public API? I have a few questions about pagination."),
    ("normal", "Vacation photos", "I uploaded the photos from the trip. Let me know if you want me to share a folder with you and the kids."),
    ("normal", "Re: Standup postponed", "Pushing today's standup to 11:30 because of a customer call. Calendar invite to follow."),
    ("normal", "Hiring update", "We interviewed three strong candidates this week. Sharing the panels' notes for the next hiring sync."),
    ("normal", "Conference next month", "I just registered for the AI conference next month in Lisbon. Let me know if you'd like to join the trip."),
    ("normal", "Re: Roadmap", "Looping back on the roadmap. I think we should defer the migration to Q3 -- see attached rationale."),
    ("normal", "Coffee tomorrow?", "Are you free for coffee tomorrow around 10? Would love to catch up on the design review."),
    ("normal", "Re: Brand assets", "Latest brand assets are uploaded to the shared drive. Use the new SVG versions for the website, please."),
    ("normal", "Welcome to the team", "Welcome aboard! Looking forward to working with you. Let's set up a 30-minute intro this week."),
    ("normal", "Re: Travel reimbursement", "Your travel reimbursement was processed. The amount will appear on the next payroll cycle."),
    ("normal", "Reading list", "Sharing a few papers I enjoyed recently. The third one is especially relevant to the workstream."),
    ("normal", "Re: Volunteer signup", "Thanks for signing up to volunteer at the school science fair next weekend. See you there at 9."),
    ("normal", "Re: Interview feedback", "Strong candidate. I leaned toward 'hire'. Sharing detailed notes so you can weigh in before Monday."),
    ("normal", "Mortgage renewal reminder", "Your mortgage is up for renewal in 90 days. We'd be happy to walk through the options when you have time."),
    ("normal", "Re: Postgres upgrade plan", "Plan looks reasonable. Could we split the read-replica cutover into its own change so we can roll back easily?"),
    ("normal", "Birthday lunch Friday", "A few of us are taking the birthday girl out for lunch on Friday. RSVP by Wednesday so I can make a reservation."),
    ("normal", "Re: Design tokens", "I pushed the latest design tokens to the front-end repo. Let me know if anything looks off on your end."),
    ("normal", "Annual review notes", "Draft of your annual review is attached. Let me know if the tone matches what you wanted before I share it."),
    ("normal", "Conference room change", "The Friday all-hands will now be in the 4th-floor conference room instead of the usual one."),

    # ===========================
    # NOTIFICATION (16 samples)
    # ===========================
    ("notification", "Your order #12345 has shipped", "Hi there, your order has shipped and is on its way. Track it here: https://example.com/track/12345"),
    ("notification", "New login from Chrome on Windows", "We detected a new login to your account from Chrome on Windows. If this was you, no action is needed."),
    ("notification", "Your monthly statement is ready", "Your statement for the month is now available in your account dashboard."),
    ("notification", "Meeting reminder: Weekly Sync", "This is a reminder that your weekly sync starts in 15 minutes. Joining link inside the calendar invite."),
    ("notification", "Password changed successfully", "Your password was recently changed. If you did not do this, please contact support right away."),
    ("notification", "Package delivered", "Your package was delivered to your front door at 2:35 PM today. No signature required."),
    ("notification", "Calendar invite: Design review", "You have been invited to Design review on Friday at 3 PM. Reply with Accept / Tentative / Decline."),
    ("notification", "Two-factor code: 382915", "Use code 382915 to finish signing in. The code expires in 10 minutes."),
    ("notification", "Your subscription renewed", "Your annual subscription was renewed successfully. The next charge will appear on the same date next year."),
    ("notification", "Flight check-in open", "Check-in for flight AB1234 is now open. Please confirm your seat before departure."),
    ("notification", "noreply: Build succeeded", "[noreply@example.com] Build #4821 succeeded. Tests passed: 312, skipped: 4, failed: 0."),
    ("notification", "GitHub: PR review requested", "alice requested your review on pull request #2147 in repo acme/web. Comments are open until Friday."),
    ("notification", "Your invoice is ready", "Invoice INV-2026-0098 is now available in your billing portal. Please review at your convenience."),
    ("notification", "Security key registered", "A new security key was added to your account. If this wasn't you, remove it from security settings immediately."),
    ("notification", "Server maintenance window", "Scheduled maintenance on the staging environment tonight from 23:00 to 01:00 UTC. Expect brief downtime."),
    ("notification", "Booking confirmation", "Your booking at Blue Bottle Cafe on Saturday at 10:30 AM is confirmed. A reminder will be sent the day before."),

    # ===========================
    # SPAM (16 samples)
    # ===========================
    ("spam", "LIMITED OFFER just for you", "Click here to claim your FREE prize! Act NOW before this offer expires. Limited time only, totally free."),
    ("spam", "Make money working from home", "Make thousands per week from your couch. No experience needed. Click here to get started today."),
    ("spam", "You've been selected!", "Congratulations, you've been selected as our lucky winner. Reply with your details to claim."),
    ("spam", "Cheap meds online", "Viagra, Cialis, and more at rock-bottom prices. Discreet shipping. Order online today."),
    ("spam", "Lose 30 lbs in 30 days", "Revolutionary weight loss pill burns fat while you sleep. Click here to try it free for 30 days."),
    ("spam", "Hot singles in your area", "Meet sexy singles near you tonight. Click here to view local profiles. No credit card required."),
    ("spam", "Crypto doubling scheme", "Send any amount of Bitcoin to the address below and you will receive DOUBLE back within 24 hours."),
    ("spam", "Free iPhone 15 Pro", "You have been randomly selected to receive a brand new iPhone 15 Pro. Pay only shipping to claim."),
    ("spam", "Work from home $5000/week", "Earn $5000/week working from home. No skills required. Sign up using my referral link below."),
    ("spam", "Cheap watches - Rolex, Omega", "Luxury watches at 90% off retail. Same quality, fraction of the price. Click here to browse."),
    ("spam", "Miracle diet pill", "Doctors hate her! This one weird trick melts belly fat overnight. Click to read the secret."),
    ("spam", "Free Netflix for 1 year", "Get a free 1-year Netflix subscription. Just complete a short survey to unlock your code."),
    ("spam", "Earn crypto by clicking", "Click ads in our app and earn crypto payouts instantly. Download our app and start earning today."),
    ("spam", "Congratulations, you won a car", "Reply to this email with your full name and address to claim your brand new Tesla Model 3."),
    ("spam", "Cheap software licenses", "90% off Microsoft Office, Adobe Creative Cloud, and more. Lifetime licenses available."),
    ("spam", "Hot deals just for you", "Massive discounts on your favorite brands. Limited stock available. Click to shop the sale now."),

    # ===========================
    # SCAM / PHISHING (24 samples)
    # ===========================
    ("scam", "URGENT: Verify your account immediately", "Dear customer, your account has been suspended. Click here to verify your account now or it will be closed within 24 hours: http://bit.ly/abc123"),
    ("scam", "Your PayPal account is locked", "We detected unusual activity. Click here to unlock your account immediately or contact us via this emergency email."),
    ("scam", "Confirm your identity within 12 hours", "Please confirm your identity within 12 hours or your account will be permanently deleted. Click the secure link to verify."),
    ("scam", "You won $5,000,000 dollars", "Dear beneficiary, your email was randomly selected to receive $5,000,000 USD. Reply with your full bank details to claim."),
    ("scam", "Wire transfer request from CEO", "Hi, I need you to wire $45,000 to this vendor today. I'm in a meeting and cannot take calls. Please treat as urgent."),
    ("scam", "Your Apple ID was used to purchase", "Your Apple ID was just used to purchase $899 worth of content. If this wasn't you, click here to cancel the purchase immediately."),
    ("scam", "Inheritance claim", "I am a lawyer representing the estate of a deceased client who left $8.5M to you. Reply with your details to claim the inheritance."),
    ("scam", "Tax refund pending", "You have a tax refund of $1,249.83 pending. Click here to verify your bank account and receive the refund within 24 hours."),
    ("scam", "Microsoft 365 password expires today", "Your Microsoft 365 password expires today. Click here now to keep your account active. Failure to act will lock you out within the hour."),
    ("scam", "Update your banking credentials", "Our bank records show your account information needs updating. Failure to update within 48 hours will result in account suspension."),
    ("scam", "Congratulations from United Nations", "The UN has approved a compensation payment of $1,200,000 to you as a scam victim. Send your details to receive the funds."),
    ("scam", "Police arrest warrant notice", "There is an outstanding arrest warrant under your name. Click here to clear the warrant before law enforcement takes action."),
    ("scam", "Your SSN has been suspended", "Your Social Security Number has been suspended due to suspicious activity. Call this number immediately to avoid legal action."),
    ("scam", "Click here to claim Bitcoin", "A wallet with 2.7 BTC is waiting for you. Click this link and enter your seed phrase to claim your funds immediately."),
    ("scam", "FedEx package awaiting pickup", "A FedEx package is waiting at our sorting facility. Pay the small customs fee of $1.99 here to release the package for delivery."),
    ("scam", "Update payment method to avoid service interruption", "Your last invoice failed. Update your credit card within 24 hours or your subscription will be permanently cancelled. Click here."),
    ("scam", "Verify your login from unknown device", "A login from an unknown device was detected. If this was NOT you, click here immediately to secure your account via two-factor reset."),
    ("scam", "Urgent request from your boss", "Are you at your desk? I need you to buy 4 Apple gift cards ($500 each) and send me the codes ASAP. Do not call, just email me back."),
    ("scam", "Your Gmail is full - click to upgrade", "Your Gmail inbox is at 99% capacity. Click here to upgrade storage and avoid losing incoming messages within the hour."),
    ("scam", "Lottery winning notification", "Your email address has been selected as the winner of the UK National Lottery ($2.5M). Forward your details and a copy of your ID to claim."),
    ("scam", "DocuSign document to sign", "You have a new DocuSign document awaiting signature. Click here to review and sign - the document expires in 24 hours."),
    ("scam", "IRS final notice before legal action", "This is your final notice from the IRS. You owe back taxes and penalties. Pay immediately via gift cards to avoid a lawsuit."),
    ("scam", "Bank fraud alert", "Fraud alert: unusual transactions detected. Verify your identity by replying with your full account number and PIN to prevent the freeze."),
    ("scam", "Your Coinbase withdrawal pending", "A withdrawal of 0.85 BTC is pending authorization. If you did not initiate this, click here to secure your wallet right now."),
]
