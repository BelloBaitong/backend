import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1772607099671 implements MigrationInterface {
    name = 'AutoMigration1772607099671'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ADD "embedding" vector`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]::text[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]::text[]`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" DROP COLUMN "embedding"`);
    }

}
