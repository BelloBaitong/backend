import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Req,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

import { ChatService } from './chat.service';

type JwtReq = Request & { user?: { id: number } };

@UseGuards(AuthGuard('jwt'))
@Controller('chat')
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  @Post('sessions')
  async createSession(
    @Req() req: JwtReq,
    @Body() body: { title?: string },
  ) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.createSession(userId, body?.title);
  }

  @Get('sessions')
  async listSessions(@Req() req: JwtReq) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.listSessions(userId);
  }

  @Get('sessions/:id/messages')
  async listMessages(@Req() req: JwtReq, @Param('id') sessionId: string) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.listMessages(userId, sessionId);
  }

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

  @Delete('sessions/:id')
  async deleteSession(@Req() req: JwtReq, @Param('id') sessionId: string) {
    const userId = req.user?.id;
    if (!userId) throw new BadRequestException('Missing user');

    return this.chatService.deleteSession(userId, sessionId);
  }
}