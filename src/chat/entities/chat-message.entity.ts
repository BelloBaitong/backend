import { Entity, PrimaryGeneratedColumn, Column, ManyToOne, CreateDateColumn } from 'typeorm';
import { ChatSession } from './chat-session.entity';

@Entity('chat_messages')
export class ChatMessage {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => ChatSession, { onDelete: 'CASCADE' })
  session: ChatSession;

  @Column()
  role: 'user' | 'assistant';

  @Column('text')
  content: string;

  @Column({ type: 'jsonb', nullable: true })
  sources: any;

  @CreateDateColumn()
  createdAt: Date;
}
