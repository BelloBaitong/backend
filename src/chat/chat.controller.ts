import {
  Body,
  Controller,
  Get,
  Param,
  Post,
  Req,
  UseGuards,
  BadRequestException,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

import { ChatService } from './chat.service';

type JwtReq = Request & { user?: { id: number } };

@UseGuards(AuthGuard('jwt'))
@Controller('chat')
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  // 1) สร้างห้องแชทใหม่
  @Post('sessions')
  async createSession(
    @Req() req: JwtReq,
    @Body() body: { title?: string },
  ) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.createSession(userId, body?.title);
  }

  // 2) list ห้องแชทของ user
  @Get('sessions')
  async listSessions(@Req() req: JwtReq) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.listSessions(userId);
  }

  // 3) ดึง messages ของห้องแชท
  @Get('sessions/:id/messages')
  async listMessages(@Req() req: JwtReq, @Param('id') sessionId: string) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.listMessages(userId, sessionId);
  }

  // 4) ส่ง message -> save user msg -> call RAG -> save assistant msg
  @Post('sessions/:id/messages')
  async sendMessage(
    @Req() req: JwtReq,
    @Param('id') sessionId: string,
    @Body() body: { content: string; topK?: number },
  ) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    const content = (body?.content ?? '').trim();
    if (!content) throw new BadRequestException('content is required');

    const topK = body?.topK ?? 3;
    return this.chatService.sendMessage(userId, sessionId, content, topK);
  }
}
