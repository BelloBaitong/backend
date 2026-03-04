import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Param,
  Delete,
  Req, Put, UseGuards
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import type { Request } from 'express';
import { UserService } from './user.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { UserProfileService } from './user-profile.service';
import { UpsertUserProfileDto } from './dto/upsert-user-profile.dto';


@Controller('user')
export class UserController {
constructor(
  private readonly userService: UserService,
  private readonly userProfileService: UserProfileService,
) {}
  @Post()
  create(@Body() createUserDto: CreateUserDto) {
    return this.userService.createUser(createUserDto);
  }

  @Get()
  findAll() {
    return this.userService.findAllUser();
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.userService.viewUser(+id);
  }

  @Patch(':id')
  update(
    @Param('id') id: string,
    @Body() updateUserDto: UpdateUserDto,
  ) {
    return this.userService.updateUser(+id, updateUserDto);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.userService.removeUser(+id);
  }

  @Get('profile/me')
    @UseGuards(AuthGuard('jwt'))
    getMyProfile(@Req() req: Request) {
    const userId = (req as any).user.id;
      return this.userProfileService.getMe(userId);
}

  @Put('profile/me')
    @UseGuards(AuthGuard('jwt'))
    upsertMyProfile(@Req() req: Request, @Body() body: UpsertUserProfileDto) {
    const userId = (req as any).user.id;
      return this.userProfileService.upsertMe(userId, body);
}
}
