# WhatsApp Official Integration Setup Guide

This project supports the official WhatsApp Cloud API (Meta). Follow these steps to set up the integration professionally.

## 1. Meta Developer Portal Setup

1.  Go to the [Meta for Developers](https://developers.facebook.com/) portal.
2.  Create a "Business" type App.
3.  Add the **WhatsApp** product to your app.
4.  In the WhatsApp configuration:
    *   Note your **Phone Number ID**.
    *   Note your **WhatsApp Business Account ID**.
    *   Generate a **Permanent Access Token** (via System User in Business Manager).
    *   Find your **App Secret** in App Settings > Basic.

## 2. Webhook Configuration

1.  Go to **WhatsApp > Configuration** in your Meta App.
2.  Set the **Callback URL** to: `https://your-domain.com/api/v1/channels/whatsapp`
3.  Set a **Verify Token** (a random string you choose).
4.  Subscribe to the `messages` webhook field.

## 3. Environment Variables

Update your `.env` file with the following:

```env
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_permanent_access_token
WHATSAPP_VERIFY_TOKEN=your_chosen_verify_token
WHATSAPP_APP_SECRET=your_app_secret
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id
WHATSAPP_API_URL=https://graph.facebook.com/v21.0
```

## 4. Professional Features Included

- **Signature Verification**: Every incoming webhook is verified using `HMAC-SHA256` with your `WHATSAPP_APP_SECRET` to ensure it comes from Meta.
- **Auto-Read Receipts**: The system automatically sends a "read" status (blue ticks) back to WhatsApp when a message is received.
- **Multi-Message Support**: Handles batches of messages in a single webhook request.
- **Media Support**: Automatically identifies and logs images, videos, audio, and documents.
- **Status Tracking**: Processes and logs message status updates (sent, delivered, read).

## 5. Security Note

Always use HTTPS for your webhook URL in production. The `WHATSAPP_APP_SECRET` ensures that only Meta can send requests to your endpoint.
