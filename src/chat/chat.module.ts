import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';

import { ChatSession } from './entities/chat-session.entity';
import { ChatMessage } from './entities/chat-message.entity';

// ต้อง import RecommendationModule เพื่อ inject RecommendationService ได้
import { RecommendationModule } from '../recommendation/recommendation.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([ChatSession, ChatMessage]),
    RecommendationModule,
  ],
  controllers: [ChatController],
  providers: [ChatService],
  exports: [ChatService],
})
export class ChatModule {}
