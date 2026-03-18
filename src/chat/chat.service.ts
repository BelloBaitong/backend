import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

import { ChatSession } from './entities/chat-session.entity';
import { ChatMessage } from './entities/chat-message.entity';

import { RecommendationService } from '../recommendation/recommendation.service';
import { User } from '../user/entities/user.entity';

@Injectable()
export class ChatService {
  constructor(
    @InjectRepository(ChatSession)
    private readonly sessionRepo: Repository<ChatSession>,

    @InjectRepository(ChatMessage)
    private readonly messageRepo: Repository<ChatMessage>,

    private readonly recommendationService: RecommendationService,
  ) {}

  async createSession(userId: number, title?: string) {
    if (!userId) throw new BadRequestException('Missing userId');

    const session = this.sessionRepo.create({
      title: (title ?? 'แชทใหม่').trim() || 'แชทใหม่',
      // ผูก user โดยอ้างอิง id ได้เลย (ไม่ต้อง query user ก่อน)
      user: { id: userId } as User,
    });

    const saved = await this.sessionRepo.save(session);
    return {
      id: saved.id,
      title: saved.title,
      createdAt: saved.createdAt,
      updatedAt: saved.updatedAt,
    };
  }

  async listSessions(userId: number) {
    if (!userId) throw new BadRequestException('Missing userId');

    const sessions = await this.sessionRepo.find({
      where: { user: { id: userId } },
      order: { updatedAt: 'DESC' },
    });

    return sessions.map((s) => ({
      id: s.id,
      title: s.title,
      createdAt: s.createdAt,
      updatedAt: s.updatedAt,
    }));
  }

  async listMessages(userId: number, sessionId: string) {
    if (!userId) throw new BadRequestException('Missing userId');
    if (!sessionId) throw new BadRequestException('Missing sessionId');

    // เช็คว่า session นี้เป็นของ user จริง
    const session = await this.sessionRepo.findOne({
      where: { id: sessionId, user: { id: userId } },
    });
    if (!session) throw new NotFoundException('Session not found');

    const msgs = await this.messageRepo.find({
      where: { session: { id: sessionId } },
      order: { createdAt: 'ASC' },
    });

    return msgs.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      sources: m.sources ?? null,
      createdAt: m.createdAt,
    }));
  }

  async sendMessage(
    userId: number,
    sessionId: string,
    content: string,
    topK: number,
  ) {
    if (!userId) throw new BadRequestException('Missing userId');
    if (!sessionId) throw new BadRequestException('Missing sessionId');
    const text = (content ?? '').trim();
    if (!text) throw new BadRequestException('content is required');

    // ต้องเป็น session ของ user เท่านั้น
    const session = await this.sessionRepo.findOne({
      where: { id: sessionId, user: { id: userId } },
    });
    if (!session) throw new NotFoundException('Session not found');

    // 1) save user message
    const userMsg = this.messageRepo.create({
      session: { id: session.id } as ChatSession,
      role: 'user',
      content: text,
      sources: null,
    });
    const savedUserMsg = await this.messageRepo.save(userMsg);

    // 2) call RAG (ผ่าน recommendation service เดิมของคุณ)
    const rag = await this.recommendationService. ragAnswer(text, topK, userId); // ส่ง userId ไปด้วย เผื่อ RAG จะใช้ข้อมูลโปรไฟล์ช่วยตอบได้ดีขึ้น

    // 3) save assistant message
    const botMsg = this.messageRepo.create({
      session: { id: session.id } as ChatSession,
      role: 'assistant',
      content: rag.answer ?? '',
      sources: rag.sources ?? null,
    });
    const savedBotMsg = await this.messageRepo.save(botMsg);

    // 4) update session.updatedAt (ให้ห้องเด้งขึ้นบนสุดใน history)
    await this.sessionRepo.update(
      { id: session.id },
      { updatedAt: new Date() },
    );

    return {
      userMessage: {
        id: savedUserMsg.id,
        role: savedUserMsg.role,
        content: savedUserMsg.content,
        createdAt: savedUserMsg.createdAt,
      },
      assistantMessage: {
        id: savedBotMsg.id,
        role: savedBotMsg.role,
        content: savedBotMsg.content,
        sources: savedBotMsg.sources ?? null,
        createdAt: savedBotMsg.createdAt,
      },
    };
  }
}
