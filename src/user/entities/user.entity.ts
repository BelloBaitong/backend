import { Entity, PrimaryGeneratedColumn, Column,OneToMany } from 'typeorm';
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

  @Column({ type: 'varchar', length: 40 })
  email: string;

  @Column({ type: 'int' })
  age: number;

  @Exclude()
  @Column({ type: 'varchar' })
  password: string;


  @Column({ type: 'enum', enum: ['m', 'f', 'u'] })
  gender: string;

  @OneToMany(() => Review, (review) => review.user)
  reviews: Review[];
}



