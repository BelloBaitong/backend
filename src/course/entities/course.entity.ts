import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, OneToMany} from 'typeorm';
import { Review } from '../../review/entities/review.entity';


export enum CourseCategory {
  ELECTIVE = 'ELECTIVE', // วิชาเลือก
  GENERAL = 'GENERAL',   // วิชาศึกษาทั่วไป
}

@Entity('course')
export class Course {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ type: 'varchar', length: 20, unique: true })
  courseCode: string; // รหัสวิชา

  @Column({ type: 'varchar', length: 255 })
  courseNameTh: string; // ชื่อวิชา

  // ✅ ชื่อวิชาภาษาอังกฤษ
  @Column({ type: 'varchar', length: 255 })
  courseNameEn: string;

  @Column({ type: 'text', nullable: true })
  description?: string; // คำอธิบายรายวิชา

  @Column({ type: 'int', default: 3 })
  credits: number; // หน่วยกิต

  @Column({ type: 'enum', enum: CourseCategory })
  category: CourseCategory; // หมวดวิชา

  @Column({ type: 'text', nullable: true })
  imageUrl?: string;
  // รูปภาพประกอบวิชา
  @CreateDateColumn()
  createdAt: Date;

  @OneToMany(() => Review, (review) => review.course)
  reviews: Review[];

}

