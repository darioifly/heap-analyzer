import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import type { Crs, Project } from "@/types";

const projectSchema = z.object({
  name: z.string().min(1, "Il nome è obbligatorio"),
  location: z.string().optional(),
  crs: z.enum(["EPSG:32632", "EPSG:32633"]),
  notes: z.string().optional(),
});

type ProjectFormData = z.infer<typeof projectSchema>;

const DEFAULT_CATEGORIES = [
  "Rottame ferroso",
  "Ghisa",
  "Scorie",
  "Cascami",
  "RAEE",
];

interface ProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project?: Project;
  onSave: (data: {
    name: string;
    location: string | null;
    crs: Crs;
    notes: string | null;
    materialCategories: string[];
  }) => void;
}

export function ProjectDialog({
  open,
  onOpenChange,
  project,
  onSave,
}: ProjectDialogProps) {
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryInput, setCategoryInput] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: "",
      location: "",
      crs: "EPSG:32632",
      notes: "",
    },
  });

  useEffect(() => {
    if (open) {
      if (project) {
        reset({
          name: project.name,
          location: project.location ?? "",
          crs: project.crs,
          notes: project.notes ?? "",
        });
        setCategories(project.materialCategories);
      } else {
        reset({ name: "", location: "", crs: "EPSG:32632", notes: "" });
        setCategories([]);
      }
      setCategoryInput("");
    }
  }, [open, project, reset]);

  const addCategory = () => {
    const trimmed = categoryInput.trim();
    if (trimmed && !categories.includes(trimmed)) {
      setCategories((prev) => [...prev, trimmed]);
      setCategoryInput("");
    }
  };

  const removeCategory = (cat: string) => {
    setCategories((prev) => prev.filter((c) => c !== cat));
  };

  const onSubmit = (data: ProjectFormData) => {
    onSave({
      name: data.name,
      location: data.location || null,
      crs: data.crs as Crs,
      notes: data.notes || null,
      materialCategories: categories,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            {project ? "Modifica progetto" : "Nuovo progetto"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Nome *</Label>
            <Input
              id="name"
              autoFocus
              placeholder="Es. Acciaieria Brescia"
              {...register("name")}
            />
            {errors.name && (
              <p className="text-xs text-danger-500">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="location">Località</Label>
            <Input
              id="location"
              placeholder="Es. Brescia, BS"
              {...register("location")}
            />
          </div>

          <div className="space-y-2">
            <Label>Sistema di riferimento</Label>
            <Select
              defaultValue={project?.crs ?? "EPSG:32632"}
              onValueChange={(v) => setValue("crs", v as Crs)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="EPSG:32632">
                  EPSG:32632 - UTM Zona 32N
                </SelectItem>
                <SelectItem value="EPSG:32633">
                  EPSG:32633 - UTM Zona 33N
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Note</Label>
            <Textarea
              id="notes"
              placeholder="Note aggiuntive..."
              rows={3}
              {...register("notes")}
            />
          </div>

          <div className="space-y-2">
            <Label>Categorie materiali</Label>
            <div className="flex gap-2">
              <Input
                value={categoryInput}
                onChange={(e) => setCategoryInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCategory();
                  }
                }}
                placeholder="Aggiungi categoria..."
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addCategory}
              >
                Aggiungi
              </Button>
            </div>

            {categories.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {categories.map((cat) => (
                  <Badge key={cat} variant="secondary" className="gap-1">
                    {cat}
                    <button
                      type="button"
                      onClick={() => removeCategory(cat)}
                      className="hover:text-danger-500"
                    >
                      <X size={12} />
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            {categories.length === 0 && (
              <div className="flex flex-wrap gap-1.5 mt-1">
                <span className="text-xs text-muted-foreground mr-1">
                  Suggeriti:
                </span>
                {DEFAULT_CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setCategories((prev) => [...prev, cat])}
                    className="text-xs text-primary hover:underline"
                  >
                    {cat}
                  </button>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Annulla
            </Button>
            <Button type="submit">Salva</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
