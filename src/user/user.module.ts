import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';  // เพิ่มบรรทัดนี้
import { UserService } from './user.service';
import { UserController } from './user.controller';
import { User } from './entities/user.entity';     // เพิ่มบรรทัดนี้

@Module({
  imports: [
    TypeOrmModule.forFeature([User])  // เพิ่มตรงนี้
  ],
  controllers: [UserController],
  providers: [UserService],
})
export class UserModule {}
