# IPL MEGA AUCTION SIMULATOR

Version: 1.0

---

# PROJECT GOAL

Build a realistic IPL Mega Auction Simulator inspired by the official IPL auction.

The simulator should feel like:

* IPL Mega Auction
* Football Manager
* Franchise Cricket Management Game

This is not a CRUD project.

The application should simulate a complete IPL Mega Auction experience.

---

# TECH STACK

Frontend:

* HTML
* CSS
* Vanilla JavaScript

Backend:

* FastAPI
* SQLAlchemy
* SQLite

Realtime:

* FastAPI WebSockets

Version Control:

* Git
* GitHub

---

# DATASETS

Uploaded Datasets:

1. players.csv
2. teams.csv
3. auction_config.json

These datasets are the source of truth.

Never generate fake players.

Never generate random teams.

Use uploaded datasets only.

---

# TEAM SELECTION FLOW

Application Start

↓

User Selects IPL Team

↓

Retention Phase

↓

AI Retentions

↓

Auction Initialization

↓

Main Auction

↓

Accelerated Auction

↓

Final Squads

↓

Results Dashboard

---

# IPL TEAMS

* Chennai Super Kings (CSK)
* Mumbai Indians (MI)
* Royal Challengers Bengaluru (RCB)
* Kolkata Knight Riders (KKR)
* Sunrisers Hyderabad (SRH)
* Delhi Capitals (DC)
* Punjab Kings (PBKS)
* Rajasthan Royals (RR)
* Gujarat Titans (GT)
* Lucknow Super Giants (LSG)

One team is controlled by the user.

Remaining teams are AI controlled.

---

# RETENTION SYSTEM

Every team starts with:

120 Crore Purse

User must retain:

Exactly 3 Players

Retention Cost Structure:

Retention 1 = 18 Cr

Retention 2 = 15 Cr

Retention 3 = 8 Cr

Total Retention Cost:

41 Cr

Remaining Purse:

79 Cr

Retained Players:

* Removed from auction
* Added directly to squad

---

# AI RETENTION SYSTEM

AI teams also retain 3 players.

Retention Logic Priority:

1. Captain
2. Higher Rated Players
3. Capped Players
4. Core Team Players

AI Retentions must not be random.

---

# AUCTION ORDER

Auction must strictly follow:

1. Marquee Set
2. Capped Batsmen
3. Capped Bowlers
4. Capped All-Rounders
5. Capped Wicket Keepers
6. Uncapped Players
7. Overseas Players
8. Accelerated Auction

Within each category:

ORDER BY auction_order ASC

Random player ordering is prohibited.

---

# PLAYER RATINGS

Each player contains:

rating

Range:

50 - 99

Used for:

* AI Retentions
* AI Bidding
* Team Strength
* Squad Quality

Higher ratings should attract stronger bidding.

---

# BIDDING ENGINE

Requirements:

Validate:

* Purse
* Squad Size
* Overseas Limits
* Duplicate Purchases

Auction must feel realistic.

Avoid random bidding behaviour.

AI should bid based on:

* Player Rating
* Squad Needs
* Remaining Purse
* Role Requirements
* Overseas Slots

---

# COUNTDOWN SYSTEM

Whenever a bid is placed:

Reset Timer

Display:

3

2

1

If no bid:

GOING ONCE

GOING TWICE

FINAL CALL

If new bid arrives:

Cancel countdown

Restart bidding

Restart timer

---

# RTM SYSTEM (RIGHT TO MATCH)

Each Team Receives:

2 RTM Cards

Eligibility:

* Player belonged to that team before auction
* Player was not retained

Auction Flow:

Example:

Mohammed Siraj

Previous Team:
RCB

Current Winning Team:
MI

Winning Bid:
12 Cr

Pause Auction

Display RTM Popup

Give RCB 4 seconds

Options:

USE RTM

DECLINE

If RTM Accepted:

* Player joins RCB
* Cost = 12 Cr
* RTM count decreases

If Declined:

* Player joins MI

Store RTM history.

---

# SQUAD CONSTRAINTS

Minimum Squad:

18 Players

Maximum Squad:

25 Players

Maximum Overseas:

8 Players

Teams cannot violate these rules.

---

# ACCELERATED AUCTION

When player pool becomes small:

Switch to Accelerated Auction

Features:

* Faster timers
* Faster nominations
* Reduced delays
* Bulk player processing

---

# TEAM STRENGTH SYSTEM

Calculate live team rating.

Factors:

* Player Ratings
* Squad Balance
* Overseas Quality
* Bench Strength
* Role Distribution

Display:

Overall Team Rating

Out of 100

Update live during auction.

---

# MY SQUAD DASHBOARD

Display:

Players Purchased

Players Retained

Role Breakdown

BAT

BOW

AR

WK

Overseas Count

Money Spent

Money Remaining

Team Rating

---

# AUCTION ROOM UI

Design Inspiration:

IPL Auction 2027 Simulator

Modern Sports Management Game

Dark Luxury Theme

---

# HEADER

Display:

IPL AUCTION SIMULATOR

Selected Team

Current Auction Round

Current Category

Lot Number

---

# LEFT PANEL

Display:

All Teams

Remaining Purse

Players Bought

Overseas Count

Remaining RTMs

Highlight Leading Bidder

---

# CENTER PANEL

Current Player Card

Display:

Player Photo

Player Name

Country

Role

Age

Rating

Current Team

Base Price

Current Bid

Leading Team

Tags:

MARQUEE

HOT PLAYER

OVERSEAS

UNCAPPED

---

# LIVE BID AREA

Display:

Current Bid

Leading Team

Countdown

Animations

---

# BID CONTROLS

Bid

Skip Player

Pause Auction

Auto Bid

Auction Speed

Normal

Fast

Very Fast

---

# RIGHT PANEL

Auction History

Recent Bids

Sold Players

Unsold Players

---

# RTM MODAL UI

Fullscreen Popup

Display:

Player Name

Previous Team

Winning Team

Winning Bid

Countdown:

4

3

2

1

Buttons:

USE RTM

DECLINE

Auto decline when timer expires.

---

# VISUAL STYLE

Background:

#0b1020

Panels:

#151d35

Gold Accent:

#FFD700

Use:

* Glassmorphism
* Smooth Animations
* Modern Dashboard Design

---

# WEBSOCKET FEATURES

Realtime Updates

Live Bids

Live Countdown

Live Purse Updates

Live RTM Events

Live Auction History

---

# COMPLETED MODULES

Architecture

Database Design

Project Structure

Team Selection Module

Retention Module

AI Retention Module

Auction Initialization Module

Datasets Finalized

GitHub Repository Created

---

# NEXT MODULES TO BUILD

1. RTM System
2. Auction Engine
3. Bid Engine
4. Countdown System
5. AI Bidding System
6. Auction Room UI
7. Premium UI Redesign
8. RTM Modal UI
9. My Squad Dashboard
10. Accelerated Auction
11. WebSockets
12. Final Testing
13. Bug Fixing
14. Deployment

---

# NON-NEGOTIABLE RULES

Never use random auction ordering.

Never use random AI retention.

Always follow auction_set.

Always follow auction_order.

Always respect squad limits.

Always respect overseas limits.

Always respect purse limits.

Always prioritize realism over simplicity.

This file is the permanent source of truth for the entire project.
