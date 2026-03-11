import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { User } from './entities/user.entity';
import { UserProfile } from './entities/user-profile.entity';
import { UserService } from './user.service';
import { UserController } from './user.controller';
import { UserProfileService } from './user-profile.service';
import { HttpModule } from '@nestjs/axios';

@Module({
  imports: [TypeOrmModule.forFeature([User, UserProfile]) 
  , HttpModule], // ✅ เพิ่ม HttpModule เพื่อให้ UserProfileService ใช้ HttpService ได้
  controllers: [UserController],
  providers: [UserService,UserProfileService],
  exports: [UserService,UserProfileService], // ✅ สำคัญ: ให้ module อื่น (AuthModule) ใช้ UserService และ UserProfileService ได้
})
export class UserModule {}
