import { Entity, PrimaryGeneratedColumn, Column, OneToMany } from 'typeorm';
import { Exclude } from 'class-transformer';
import { Review } from '../../review/entities/review.entity';

@Entity()
export class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'varchar', length: 30 })
  name: string;

  @Column({ type: 'varchar', length: 15 })
  username: string;

  @Column({ type: 'varchar', length: 40, unique: true })
  email: string;

  // ✅ Google ไม่มี age → ต้อง nullable
  @Column({ type: 'int', nullable: true })
  age: number | null;

  // ✅ Google ไม่มี password → ต้อง nullable
  @Exclude()
  @Column({ type: 'varchar', nullable: true })
  password: string | null;

  // ✅ ให้มีค่า default เผื่อ Google
  @Column({ type: 'enum', enum: ['m', 'f', 'u'], default: 'u' })
  gender: string;

  @OneToMany(() => Review, (review) => review.user)
  reviews: Review[];

  // ✅ เพิ่มกลับมา (คุณใช้ใน createGoogleUser อยู่)
  @Column({ type: 'varchar', nullable: true })
  provider: string | null;

  @Column({ type: 'varchar', nullable: true })
  providerId: string | null;

  @Column({ type: 'text', nullable: true })
  picture: string | null;
}
