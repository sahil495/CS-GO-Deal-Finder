# CS:GO Deal Finder 

A powerful, real-time desktop bot to find **profitable CS:GO skin deals** on [CSFloat.com](https://csfloat.com) using live scraping, smart filtering, and alerts — all packed into a beautiful PyQt interface.

---

##  Features

-  **Real-time scraping** of newly listed CS:GO skins from CSFloat
-  **Profit calculator** with customizable platform fee and min/max price
-  **Audio + visual alerts** for hot, profitable deals
-  **BetterFloat Support**: Uses accurate float + pricing insights from BetterFloat Chrome Extension
-  **Custom filters**: Set minimum profit, price range, and fees
-  **Direct purchase links**: One-click "Buy Now" opens the deal on CSFloat
-  **Dark Mode UI** for comfortable extended use
-  Includes **BetterFloat-Chrome-Web-Store** folder for enhanced pricing tools

---

## 📦 Folder: `BetterFloat-Chrome-Web-Store`

This folder contains a **modified Chrome extension** for BetterFloat, enabling:
- Auto-fetching accurate average market prices and float values
- Improved profit calculation logic for every deal
- Local access to extension features during scraping

> Use this folder to load the extension in a Chromium-based browser manually if needed.

---

##  First-Time Setup (Important!)

Before you can start sniping deals, you **must log in manually** to your [CSFloat](https://csfloat.com) or **Steam account** using the embedded browser window the first time you run the app.  
> This step is required for the bot to access and monitor live listings linked to your session.

---

##  Starting the Bot

1. Launch the app and wait for the UI to load.
2. Click the **“Start”** button — the bot will begin scraping CSFloat for newly listed CS:GO skins.
3. The app automatically **refreshes every 30 seconds** to fetch the latest deals.

---

##  Customize Your Settings

Press **Ctrl + S** or click the **“Settings”** button to open the configuration panel. Here you can adjust:

- ** Minimum / Maximum Price**  
  Set your target price range for skins (e.g., `$1 – $100`)

- ** Minimum Profit**  
  Only show deals with profit above your set threshold (e.g., `$2` or `20%`)

- ** Platform Fee**  
  Enter the marketplace fee (e.g., `5%`) to calculate net profit accurately

Click **“Apply Conditions”** to activate filters, or **“Remove Conditions”** to view all deals again.

---

##  Viewing & Sniping Deals

- All matching deals appear in the **scrollable list** in the main UI.
- The **most profitable recent deal** is shown in the right-side highlight panel.
- Click **“Buy Now”** on any card to open that skin’s page directly on CSFloat.

---

##  Alerts

-  **Sound Notification**: Plays when a new profitable deal is found
-  **Visual Highlight**: New deals are visually emphasized with color effects



