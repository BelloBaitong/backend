import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { User } from './entities/user.entity';
import { UserProfile } from './entities/user-profile.entity';
import { UserService } from './user.service';
import { UserController } from './user.controller';
import { UserProfileService } from './user-profile.service';

@Module({
  imports: [TypeOrmModule.forFeature([User, UserProfile])],
  controllers: [UserController],
  providers: [UserService,UserProfileService],
  exports: [UserService,UserProfileService], // ✅ สำคัญ: ให้ module อื่น (AuthModule) ใช้ UserService และ UserProfileService ได้
})
export class UserModule {}
