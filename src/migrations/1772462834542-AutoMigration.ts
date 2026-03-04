import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1772462834542 implements MigrationInterface {
    name = 'AutoMigration1772462834542'

    public async up(queryRunner: QueryRunner): Promise<void> {
        // เปลี่ยนความยาวจาก 15 → 30 โดยไม่ลบข้อมูล
        await queryRunner.query(
            `ALTER TABLE "user" ALTER COLUMN "username" TYPE character varying(30)`
        );
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        // ย้อนกลับ 30 → 15
        await queryRunner.query(
            `ALTER TABLE "user" ALTER COLUMN "username" TYPE character varying(15)`
        );
    }
}