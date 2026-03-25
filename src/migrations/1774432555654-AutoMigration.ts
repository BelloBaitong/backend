import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1774432555654 implements MigrationInterface {
    name = 'AutoMigration1774432555654'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ADD "completedCourseIds" integer array NOT NULL DEFAULT '{}'`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]::text[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]::text[]`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" DROP COLUMN "completedCourseIds"`);
    }

}
