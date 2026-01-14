import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn } from 'typeorm';

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
  courseName: string; // ชื่อวิชา

  @Column({ type: 'text', nullable: true })
  description?: string; // คำอธิบายรายวิชา

  @Column({ type: 'int', default: 3 })
  credits: number; // หน่วยกิต

  @Column({ type: 'enum', enum: CourseCategory })
  category: CourseCategory; // หมวดวิชา

  @CreateDateColumn()
  createdAt: Date;
}
