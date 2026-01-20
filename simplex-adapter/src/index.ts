/**
 * SimpleX Adapter Service
 * 
 * Uses the simplex-chat npm package (6.5.0-beta) which embeds
 * the chat core directly as a native Node.js addon.
 */

import express from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { WebSocket, WebSocketServer } from 'ws';
import { T } from '@simplex-chat/types';
import { bot, api, util } from 'simplex-chat';

const ADAPTER_PORT = parseInt(process.env.ADAPTER_PORT || '3000', 10);
const BOT_NAME = process.env.BOT_NAME || 'Boltz Pro Fee Bot';
const DB_FILE_PREFIX = process.env.DB_FILE_PREFIX || './simplex_bot';

function loadBotAvatar(): string | undefined {
  const avatarPath = path.join(__dirname, '..', 'bot-avatar.png');
  if (fs.existsSync(avatarPath)) {
    const pngContent = fs.readFileSync(avatarPath);
    return `data:image/png;base64,${pngContent.toString('base64')}`;
  }
  return undefined;
}

interface AdapterEvent {
  type: string;
  contactId?: number;
  displayName?: string;
  text?: string;
  messageId?: number;
}

class SimplexAdapter {
  private chat: api.ChatApi | null = null;
  private wsClients: Set<WebSocket> = new Set();
  private app = express();
  private wss: WebSocketServer | null = null;

  constructor() {
    this.app.use(express.json());
    this.setupHttpRoutes();
  }

  private setupHttpRoutes() {
    this.app.get('/health', (req, res) => {
      res.json({ 
        status: this.chat ? 'connected' : 'disconnected',
        clients: this.wsClients.size 
      });
    });

    this.app.post('/send', async (req, res) => {
      const { contactId, text } = req.body;
      
      if (!contactId || !text) {
        return res.status(400).json({ error: 'contactId and text are required' });
      }

      if (!this.chat) {
        return res.status(503).json({ error: 'Not connected to SimpleX' });
      }

      const parsedContactId = parseInt(contactId, 10);
      
      if (isNaN(parsedContactId) || parsedContactId <= 0) {
        return res.status(400).json({ error: 'Invalid contactId' });
      }

      // Test mode: contact IDs >= 90000 are fake test contacts
      // Just broadcast the response without actually sending via SimpleX
      if (parsedContactId >= 90000) {
        console.log(`[TEST] Sending to test contact ${parsedContactId}: ${text}`);
        this.broadcastEvent({
          type: 'botResponse',
          contactId: parsedContactId,
          text,
          messageId: Date.now(),
        });
        return res.json({ success: true });
      }

      try {
        const chatRef: [T.ChatType, number] = [T.ChatType.Direct, parsedContactId];
        await this.chat.apiSendTextMessage(chatRef, text);
        
        // Broadcast outgoing message for test clients to intercept
        this.broadcastEvent({
          type: 'botResponse',
          contactId: parsedContactId,
          text,
          messageId: Date.now(),
        });
        
        res.json({ success: true });
      } catch (error: any) {
        console.error(`Error sending message to ${contactId}:`, error);
        res.status(500).json({ error: String(error) });
      }
    });

    this.app.get('/address', async (req, res) => {
      if (!this.chat) {
        return res.status(503).json({ error: 'Not connected to SimpleX' });
      }

      try {
        const response = await this.chat.sendChatCmd('/show_address');
        res.json({ address: response });
      } catch (error) {
        console.error('Error getting address:', error);
        res.status(500).json({ error: String(error) });
      }
    });

    this.app.get('/contacts', async (req, res) => {
      if (!this.chat) {
        return res.status(503).json({ error: 'Not connected to SimpleX' });
      }

      try {
        const response = await this.chat.sendChatCmd('/contacts');
        res.json(response);
      } catch (error) {
        console.error('Error getting contacts:', error);
        res.status(500).json({ error: String(error) });
      }
    });

    // TEST ENDPOINT: Simulate an incoming message for e2e testing
    // Only available in non-production environments
    if (process.env.NODE_ENV !== 'production') {
      this.app.post('/test/simulate_message', async (req, res) => {
        const { contactId, displayName, text } = req.body;
        
        if (!contactId || !text) {
          return res.status(400).json({ error: 'contactId and text are required' });
        }

        console.log(`[TEST] Simulating message from ${displayName} (${contactId}): ${text}`);

        // Broadcast the message as if it came from a real contact
        this.broadcastEvent({
          type: 'newMessage',
          contactId: parseInt(contactId, 10),
          displayName: displayName || 'TestUser',
          text,
          messageId: Date.now(),
        });

        res.json({ success: true });
      });
    }
  }

  private broadcastEvent(event: AdapterEvent) {
    const message = JSON.stringify(event);
    for (const client of this.wsClients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }

  async startBot(): Promise<void> {
    console.log('Starting SimpleX bot with embedded chat core...');
    console.log(`Bot name: ${BOT_NAME}`);
    console.log(`Database prefix: ${DB_FILE_PREFIX}`);
    
    const welcomeMessage = 'Welcome! I am the Boltz Pro Fee Alert Bot.\n\nUse /help to see available commands.';
    const botAvatar = loadBotAvatar();

    try {
      const [chatApi, user, address] = await bot.run({
        profile: { displayName: BOT_NAME, fullName: '', image: botAvatar },
        dbOpts: { dbFilePrefix: DB_FILE_PREFIX, dbKey: '' },
        options: {
          createAddress: true,
          addressSettings: { 
            autoAccept: true, 
            welcomeMessage,
            businessAddress: false 
          },
          commands: [
            { type: 'command', keyword: 'help', label: 'Show available commands' },
            { type: 'command', keyword: 'subscribe', label: 'Subscribe to fee alerts' },
            { type: 'command', keyword: 'mysubscriptions', label: 'View your subscriptions' },
            { type: 'command', keyword: 'unsubscribe', label: 'Unsubscribe from alerts' },
          ],
          logContacts: true,
          logNetwork: false
        },
        onMessage: async (chatItem, content) => {
          const text = content.text || '';
          if (!text) return;

          // Skip commands - they are handled by onCommands
          if (text.startsWith('/')) return;

          const contactId = this.getContactId(chatItem);
          const displayName = this.getDisplayName(chatItem);
          const messageId = chatItem.chatItem.meta?.itemId;

          console.log(`Message from ${displayName} (${contactId}): ${text}`);

          // Broadcast to Python bot (plain text messages only)
          this.broadcastEvent({
            type: 'newMessage',
            contactId,
            displayName,
            text,
            messageId,
          });
        },
        onCommands: {
          // All commands are forwarded to Python bot
          '': async (chatItem: T.AChatItem, cmd: util.BotCommand) => {
            const contactId = this.getContactId(chatItem);
            const displayName = this.getDisplayName(chatItem);
            const text = `/${cmd.keyword}${cmd.params ? ' ' + cmd.params : ''}`;
            const messageId = chatItem.chatItem.meta?.itemId;

            console.log(`Command from ${displayName} (${contactId}): ${text}`);

            this.broadcastEvent({
              type: 'newMessage',
              contactId,
              displayName,
              text,
              messageId,
            });
          }
        },
        events: {
          'contactConnected': (event) => {
            const contact = (event as any).contact;
            if (contact) {
              console.log(`Contact connected: ${contact.profile?.displayName} (ID: ${contact.contactId})`);
              this.broadcastEvent({
                type: 'contactConnected',
                contactId: contact.contactId,
                displayName: contact.profile?.displayName || 'Unknown',
              });
            }
          }
        }
      });

      this.chat = chatApi;
      
      console.log(`Bot profile: ${user.profile.displayName}`);
      if (address) {
        console.log(`Bot address created/found`);
      }
      console.log('SimpleX bot is ready!');
      
    } catch (error) {
      console.error('Failed to start SimpleX bot:', error);
      throw error;
    }
  }

  private getContactId(chatItem: T.AChatItem): number {
    const chatInfo = chatItem.chatInfo as any;
    return chatInfo.contact?.contactId || 0;
  }

  private getDisplayName(chatItem: T.AChatItem): string {
    const chatInfo = chatItem.chatInfo as any;
    return chatInfo.contact?.profile?.displayName || 'Unknown';
  }

  async start(): Promise<void> {
    // Start HTTP server
    const server = this.app.listen(ADAPTER_PORT, () => {
      console.log(`HTTP server listening on port ${ADAPTER_PORT}`);
    });

    // Start WebSocket server for event streaming
    this.wss = new WebSocketServer({ server });
    
    this.wss.on('connection', (ws) => {
      console.log('Python bot connected via WebSocket');
      this.wsClients.add(ws);
      
      ws.on('close', () => {
        console.log('Python bot disconnected');
        this.wsClients.delete(ws);
      });

      ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        this.wsClients.delete(ws);
      });
    });

    // Start the bot with embedded chat core
    await this.startBot();
  }
}

// Main entry point
const adapter = new SimplexAdapter();
adapter.start().catch(console.error);
