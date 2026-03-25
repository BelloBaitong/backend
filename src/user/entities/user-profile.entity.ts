import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  OneToOne,
  JoinColumn,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';
import { User } from './user.entity';

@Entity('user_profile')
export class UserProfile {
  @PrimaryGeneratedColumn()
  id: number;

  // 1 user มี 1 profile (unique)
  @Column({ type: 'int', unique: true })
  userId: number;

  @OneToOne(() => User, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'userId' })
  user: User;

  @Column({ type: 'int', nullable: true })
  studyYear: number | null;

  // ใช้ text[] (Postgres)
  @Column({ type: 'text', array: true, default: () => 'ARRAY[]::text[]' })
  interests: string[];

  @Column({ type: 'text', array: true, default: () => 'ARRAY[]::text[]' })
  careerGoals: string[];

  @Column('int', { array: true, default: () => "'{}'" })
  completedCourseIds: number[];

  @Column({ type: 'vector', nullable: true })
  embedding: number[] | null;

  @CreateDateColumn({ type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updatedAt: Date;


}